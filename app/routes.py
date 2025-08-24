# routes.py
from flask import Blueprint, request, jsonify, send_from_directory
from app.models import User, Card
from pydantic import ValidationError
import jwt
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Attr
import boto3
import uuid
from app.services_utils import hash_password
from app.config import Config
from functools import wraps
import os

# ---- Uploads (S3) ----
from app.storage import upload_image, delete_image_by_url  # <- crie app/storage.py conforme instruções

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")

# ---- DynamoDB ----
dynamodb = boto3.resource(
    "dynamodb",
    region_name=Config.AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)
users_table = dynamodb.Table("GetiCardUsers")
cards_table = dynamodb.Table("Testecard")   # ajuste se o nome da sua tabela for outro

routes = Blueprint("api", __name__)
SECRET_KEY = Config.SECRET_KEY


# ---------- Helpers ----------
def _abs_url(u: str) -> str:
    """
    Se for um caminho legado (/uploads/...), retorna URL absoluta do backend.
    Se já for http(s), devolve como está.
    """
    if not u:
        return u
    if u.startswith("http://") or u.startswith("https://"):
        return u
    base = request.host_url.rstrip("/")  # https://seu-backend
    if u.startswith("/"):
        return f"{base}{u}"
    return f"{base}/{u}"

def _clean_dict(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ---------- Auth decorator ----------
def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Token ausente"}), 401
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_email = payload.get("sub")
        except Exception as e:
            return jsonify({"error": str(e)}), 403
        return f(user_email, *args, **kwargs)
    return decorator


# ---------- Register ----------
@routes.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        user = User(**data)
        user_dict = user.dict()
        user_dict["password"] = hash_password(user_dict["password"])

        if users_table.get_item(Key={"email": user_dict["email"]}).get("Item"):
            return jsonify({"error": "Usuário já existe"}), 409

        users_table.put_item(Item=user_dict)
        return jsonify({"message": "Usuário criado com sucesso"}), 201
    except ValidationError as e:
        return jsonify(e.errors()), 400
    except Exception as e:
        print("Erro ao registrar:", e)
        return jsonify({"error": str(e)}), 500


# ---------- Login ----------
@routes.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    resp = users_table.get_item(Key={"email": email})
    user = resp.get("Item")
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 401
    if user["password"] != hash_password(password):
        return jsonify({"error": "Senha inválida"}), 401

    token = jwt.encode(
        {"sub": email, "exp": datetime.utcnow() + timedelta(minutes=60)},
        SECRET_KEY,
        algorithm="HS256",
    )

    card_resp = cards_table.scan(FilterExpression=Attr("emailContato").eq(email))
    cards = card_resp.get("Items", [])
    card_id = cards[0]["card_id"] if cards else None

    return jsonify({"access_token": token, "card_id": card_id}), 200


# ---------- Create Card ----------
@routes.route("/card", methods=["POST"])
def create_card():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            form = request.form

            emailContato = form.get("emailContato")
            if not emailContato:
                return jsonify({"error": "Email para contato obrigatório!"}), 400

            # 1 cartão por e-mail
            resp = cards_table.scan(FilterExpression=Attr("emailContato").eq(emailContato))
            if resp.get("Items"):
                card_existente = resp["Items"][0]
                return jsonify({
                    "message": "Já existe um cartão para este email.",
                    "card_id": card_existente["card_id"],
                }), 200

            card_id = f"card-{uuid.uuid4().hex[:8]}"

            # Avatar -> S3
            foto_perfil_url = ""
            avatar = request.files.get("foto_perfil")
            if avatar and avatar.filename:
                foto_perfil_url = upload_image(avatar, key_prefix=f"cards/{card_id}/avatar")

            # Galeria -> S3
            galeria_urls = []
            for f in request.files.getlist("galeria"):
                if f and f.filename:
                    galeria_urls.append(upload_image(f, key_prefix=f"cards/{card_id}/galeria"))

            card_dict = _clean_dict({
                "card_id": card_id,
                "nome": form.get("nome"),
                "biografia": form.get("biografia"),
                "empresa": form.get("empresa"),
                "whatsapp": form.get("whatsapp"),
                "emailContato": emailContato,
                "instagram": form.get("instagram"),
                "linkedin": form.get("linkedin"),
                "site": form.get("site"),
                "chave_pix": form.get("chave_pix"),
                "foto_perfil": foto_perfil_url,  # URL completa (S3)
                "galeria": galeria_urls,        # lista de URLs completas (S3)
            })
            cards_table.put_item(Item=card_dict)
            return jsonify({"message": "Cartão criado com sucesso", "card_id": card_id}), 201

        # JSON fallback (sem imagens)
        data = request.json
        emailContato = data.get("emailContato")
        if not emailContato:
            return jsonify({"error": "Email para contato obrigatório!"}), 400

        resp = cards_table.scan(FilterExpression=Attr("emailContato").eq(emailContato))
        if resp.get("Items"):
            card_existente = resp["Items"][0]
            return jsonify({
                "message": "Já existe um cartão para este email.",
                "card_id": card_existente["card_id"],
            }), 200

        card_id = f"card-{uuid.uuid4().hex[:8]}"
        card = Card(**data)
        card_dict = card.dict()
        card_dict["card_id"] = card_id
        cards_table.put_item(Item=card_dict)
        return jsonify({"message": "Cartão criado com sucesso", "card_id": card_id}), 201

    except ValidationError as e:
        return jsonify(e.errors()), 400
    except Exception as e:
        print("Erro ao criar cartão:", e)
        return jsonify({"error": str(e)}), 500


# ---------- Get Card ----------
@routes.route("/card/<card_id>", methods=["GET"])
def get_card(card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        item = response.get("Item")
        if not item:
            return jsonify({"error": "Cartão não encontrado"}), 404

        # Normaliza legados (/uploads/...) para URL absoluta; S3 (http) fica como está
        if item.get("foto_perfil"):
            item["foto_perfil"] = _abs_url(item["foto_perfil"])
        if isinstance(item.get("galeria"), list):
            item["galeria"] = [_abs_url(u) for u in item.get("galeria")]

        return jsonify(item), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Update Card ----------
@routes.route("/card/<card_id>", methods=["PUT"])
@token_required
def update_card(user_email, card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        card = response.get("Item")
        if not card:
            return jsonify({"error": "Cartão não encontrado"}), 404

        # Permissão: apenas o dono
        if card.get("emailContato") != user_email:
            return jsonify({"error": "Acesso negado: você não é o dono deste cartão."}), 403

        if request.content_type and request.content_type.startswith("multipart/form-data"):
            form = request.form

            # Campos de texto
            for campo in ["nome", "biografia", "empresa", "whatsapp", "emailContato", "instagram", "linkedin", "site", "chave_pix"]:
                if campo in form:
                    card[campo] = form.get(campo)

            # Avatar novo -> S3 (opcional: remover o antigo)
            new_avatar = request.files.get("foto_perfil")
            if new_avatar and new_avatar.filename:
                # delete_image_by_url(card.get("foto_perfil"))  # descomente se quiser apagar o antigo
                card["foto_perfil"] = upload_image(new_avatar, key_prefix=f"cards/{card_id}/avatar")

            # Novas imagens da galeria
            new_urls = []
            for f in request.files.getlist("galeria"):
                if f and f.filename:
                    new_urls.append(upload_image(f, key_prefix=f"cards/{card_id}/galeria"))

            # Controle: anexar ou substituir
            replace = form.get("replace_gallery", "").lower() in ("1", "true", "yes")
            if new_urls:
                if replace:
                    card["galeria"] = new_urls
                else:
                    card["galeria"] = (card.get("galeria") or []) + new_urls

            cards_table.put_item(Item=card)
            return jsonify({"message": "Cartão atualizado com sucesso"}), 200

        # JSON fallback (sem imagens)
        data = request.json or {}
        for campo in ["nome", "biografia", "empresa", "whatsapp", "emailContato", "instagram", "linkedin", "site", "chave_pix", "foto_perfil", "galeria"]:
            if campo in data:
                card[campo] = data[campo]

        cards_table.put_item(Item=card)
        return jsonify({"message": "Cartão atualizado com sucesso"}), 200

    except Exception as e:
        print("Erro ao atualizar cartão:", e)
        return jsonify({"error": str(e)}), 500


# ---------- Delete Card ----------
@routes.route("/card/<card_id>", methods=["DELETE"])
@token_required
def delete_card(user_email, card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        card = response.get("Item")
        if not card:
            return jsonify({"error": "Cartão não encontrado"}), 404

        if card.get("emailContato") != user_email:
            return jsonify({"error": "Acesso negado: você não é o dono deste cartão."}), 403

        # (Opcional) limpar imagens do S3
        try:
            if card.get("foto_perfil"):
                delete_image_by_url(card["foto_perfil"])
            for u in card.get("galeria") or []:
                delete_image_by_url(u)
        except Exception:
            pass

        cards_table.delete_item(Key={"card_id": card_id})
        return jsonify({"message": "Cartão excluído com sucesso"}), 200
    except Exception as e:
        print("Erro ao excluir cartão:", e)
        return jsonify({"error": str(e)}), 500


# ---------- Servir uploads legados ----------
@routes.route("/uploads/<path:filename>")
def servir_arquivo(filename):
    # apenas para compatibilidade com arquivos antigos em disco
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------- Rota protegida de teste ----------
@routes.route("/segredo", methods=["GET"])
@token_required
def segredo(user_email):
    return jsonify({"mensagem": f"Você tem acesso autorizado como {user_email}"}), 200


# ---------- Debug Dynamo (opcional) ----------
@routes.route("/debug-dynamo", methods=["GET"])
def debug_dynamo():
    try:
        response = cards_table.scan()
        return jsonify(response.get("Items", [])), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
