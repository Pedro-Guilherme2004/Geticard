#routes.py

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
import os

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')

# Conexão com DynamoDB
dynamodb = boto3.resource(
    'dynamodb',
    region_name=Config.AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
users_table = dynamodb.Table("GetiCardUsers")
cards_table = dynamodb.Table("Testecard")  # Ou "GetiCardCards" se preferir

routes = Blueprint("api", __name__)
SECRET_KEY = Config.SECRET_KEY

# ------- Função utilitária para salvar imagens local -------
def salvar_imagem_local(file, filename):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return f"/uploads/{filename}"

# --------------- AUTH DECORATOR -----------------
from functools import wraps
def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Token ausente'}), 401
        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user_email = payload.get("sub")
        except Exception as e:
            return jsonify({'error': str(e)}), 403
        return f(user_email, *args, **kwargs)
    return decorator

# ------------------ REGISTRO USUÁRIO ------------------
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

# ------------------ LOGIN USUÁRIO ------------------
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

    token = jwt.encode({
        "sub": email,
        "exp": datetime.utcnow() + timedelta(minutes=60)
    }, SECRET_KEY, algorithm="HS256")

    card_resp = cards_table.scan(FilterExpression=Attr('emailContato').eq(email))
    cards = card_resp.get('Items', [])
    card_id = cards[0]["card_id"] if cards else None

    return jsonify({"access_token": token, "card_id": card_id}), 200

# ------------------ CRIAR CARTÃO ------------------
@routes.route("/card", methods=["POST"])
def create_card():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            form = request.form
            files = request.files

            emailContato = form.get("emailContato")
            if not emailContato:
                return jsonify({"error": "Email para contato obrigatório!"}), 400
            resp = cards_table.scan(
                FilterExpression=Attr('emailContato').eq(emailContato)
            )
            if resp.get('Items'):
                card_existente = resp['Items'][0]
                return jsonify({
                    "message": "Já existe um cartão para este email.",
                    "card_id": card_existente["card_id"]
                }), 200

            card_id = f"card-{uuid.uuid4().hex[:8]}"

            # Salvar foto_perfil em local
            foto_perfil_filename = ""
            if "foto_perfil" in files and files["foto_perfil"]:
                avatar = files["foto_perfil"]
                ext = avatar.filename.rsplit(".", 1)[-1].lower()
                avatar_filename = f"{card_id}_avatar.{ext}"
                foto_perfil_filename = salvar_imagem_local(avatar, avatar_filename)

            # Salvar galeria em local
            galeria_filenames = []
            galeria_files = request.files.getlist("galeria")
            for idx, img in enumerate(galeria_files):
                ext = img.filename.rsplit(".", 1)[-1].lower()
                gallery_filename = f"{card_id}_gallery{idx}.{ext}"
                galeria_filenames.append(salvar_imagem_local(img, gallery_filename))

            card_dict = {
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
                "foto_perfil": foto_perfil_filename,
                "galeria": galeria_filenames,
            }
            card_dict = {k: v for k, v in card_dict.items() if v is not None}
            cards_table.put_item(Item=card_dict)
            return jsonify({"message": "Cartão criado com sucesso", "card_id": card_id}), 201
        else:
            # Fallback para JSON (igual antes)
            data = request.json
            emailContato = data.get("emailContato")
            if not emailContato:
                return jsonify({"error": "Email para contato obrigatório!"}), 400
            resp = cards_table.scan(
                FilterExpression=Attr('emailContato').eq(emailContato)
            )
            if resp.get('Items'):
                card_existente = resp['Items'][0]
                return jsonify({
                    "message": "Já existe um cartão para este email.",
                    "card_id": card_existente["card_id"]
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

# ------------------ GET CARD ------------------
@routes.route("/card/<card_id>", methods=["GET"])
def get_card(card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        item = response.get("Item")
        if not item:
            return jsonify({"error": "Cartão não encontrado"}), 404
        return jsonify(item), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ UPDATE CARD (protegido) ------------------
@routes.route("/card/<card_id>", methods=["PUT"])
@token_required
def update_card(user_email, card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        card = response.get("Item")
        if not card:
            return jsonify({"error": "Cartão não encontrado"}), 404

        # Protege: só dono pode editar
        if card.get("emailContato") != user_email:
            return jsonify({"error": "Acesso negado: você não é o dono deste cartão."}), 403

        if request.content_type and request.content_type.startswith("multipart/form-data"):
            form = request.form
            files = request.files

            campos_editaveis = ["nome", "biografia", "empresa", "whatsapp", "emailContato", "instagram", "linkedin", "site", "chave_pix"]
            for campo in campos_editaveis:
                if campo in form:
                    card[campo] = form.get(campo)
            # Atualiza foto_perfil em local
            if "foto_perfil" in files and files["foto_perfil"]:
                avatar = files["foto_perfil"]
                ext = avatar.filename.rsplit(".", 1)[-1].lower()
                avatar_filename = f"{card_id}_avatar.{ext}"
                card["foto_perfil"] = salvar_imagem_local(avatar, avatar_filename)

            # Atualiza galeria
            galeria_filenames = []
            galeria_files = request.files.getlist("galeria")
            for idx, img in enumerate(galeria_files):
                ext = img.filename.rsplit(".", 1)[-1].lower()
                gallery_filename = f"{card_id}_gallery{idx}.{ext}"
                galeria_filenames.append(salvar_imagem_local(img, gallery_filename))
            if galeria_filenames:
                card["galeria"] = galeria_filenames

            cards_table.put_item(Item=card)
            return jsonify({"message": "Cartão atualizado com sucesso"}), 200
        else:
            # Fallback para JSON (igual antes)
            data = request.json

            campos_editaveis = ["nome", "biografia", "empresa", "whatsapp", "emailContato", "instagram", "linkedin", "site", "chave_pix", "foto_perfil", "galeria"]
            for campo in campos_editaveis:
                if campo in data:
                    card[campo] = data[campo]

            cards_table.put_item(Item=card)
            return jsonify({"message": "Cartão atualizado com sucesso"}), 200
    except Exception as e:
        print("Erro ao atualizar cartão:", e)
        return jsonify({"error": str(e)}), 500

# ------------------ DELETE CARD (protegido) ------------------
@routes.route("/card/<card_id>", methods=["DELETE"])
@token_required
def delete_card(user_email, card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        card = response.get("Item")
        if not card:
            return jsonify({"error": "Cartão não encontrado"}), 404

        # Protege: só dono pode excluir
        if card.get("emailContato") != user_email:
            return jsonify({"error": "Acesso negado: você não é o dono deste cartão."}), 403

        cards_table.delete_item(Key={"card_id": card_id})
        return jsonify({"message": "Cartão excluído com sucesso"}), 200
    except Exception as e:
        print("Erro ao excluir cartão:", e)
        return jsonify({"error": str(e)}), 500

# ------------------ UPLOADS ------------------
@routes.route("/uploads/<path:filename>")
def servir_arquivo(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ------------------ SEGREDO (PROTEGIDO) ------------------
@routes.route("/segredo", methods=["GET"])
@token_required
def segredo(user_email):
    return jsonify({"mensagem": f"Você tem acesso autorizado como {user_email}"}), 200

# ------------------ DEBUG DYNAMO (opcional) ------------------
@routes.route("/debug-dynamo", methods=["GET"])
def debug_dynamo():
    try:
        response = cards_table.scan()
        print("Itens da tabela:", response.get("Items", []))
        return jsonify(response.get("Items", [])), 200
    except Exception as e:
        print("Erro DynamoDB:", str(e))
        return jsonify({"error": str(e)}), 500
