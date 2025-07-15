#routes.py

from flask import Blueprint, request, jsonify, send_from_directory
from app.models import User, Card
from pydantic import ValidationError
import jwt
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Attr
import boto3
import uuid
from app.services import (
    hash_password,
    salvar_imagem_local,
)
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

# ------------------ REGISTRO USUÁRIO ------------------
@routes.route("/register", methods=["POST"])
def register():
    try:
        data = request.json
        user = User(**data)
        user_dict = user.dict()
        user_dict["password"] = hash_password(user_dict["password"])

        # Verifica se já existe usuário com esse e-mail
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

    # Busca usuário na tabela de usuários
    resp = users_table.get_item(Key={"email": email})
    user = resp.get("Item")
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 401
    if user["password"] != hash_password(password):
        return jsonify({"error": "Senha inválida"}), 401

    token = jwt.encode({
        "sub": email,
        "exp": datetime.utcnow() + timedelta(minutes=15)
    }, SECRET_KEY, algorithm="HS256")

    # Busca cartão associado ao emailContato do usuário (importante: emailContato, não email de login)
    card_resp = cards_table.scan(FilterExpression=Attr('emailContato').eq(email))
    cards = card_resp.get('Items', [])
    card_id = cards[0]["card_id"] if cards else None

    return jsonify({"access_token": token, "card_id": card_id}), 200

# ------------------ CRIAR CARTÃO ------------------
@routes.route("/card", methods=["POST"])
def create_card():
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            # Recebe arquivo e campos do form
            form = request.form
            files = request.files
            # Verifica se já existe cartão para este emailContato
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
            # Salva foto_perfil
            foto_perfil_filename = ""
            if "foto_perfil" in files and files["foto_perfil"]:
                avatar = files["foto_perfil"]
                ext = avatar.filename.rsplit(".", 1)[-1].lower()
                avatar_filename = f"{card_id}_avatar.{ext}"
                avatar_path = os.path.join(UPLOAD_FOLDER, avatar_filename)
                avatar.save(avatar_path)
                foto_perfil_filename = f"/uploads/{avatar_filename}"

            # Salva galeria
            galeria_filenames = []
            galeria_files = request.files.getlist("galeria")
            for idx, img in enumerate(galeria_files):
                ext = img.filename.rsplit(".", 1)[-1].lower()
                gallery_filename = f"{card_id}_gallery{idx}.{ext}"
                gallery_path = os.path.join(UPLOAD_FOLDER, gallery_filename)
                img.save(gallery_path)
                galeria_filenames.append(f"/uploads/{gallery_filename}")

            # Monta o dict do cartão (só pega campos previstos)
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
            # Remove valores None
            card_dict = {k: v for k, v in card_dict.items() if v is not None}
            cards_table.put_item(Item=card_dict)
            return jsonify({"message": "Cartão criado com sucesso", "card_id": card_id}), 201
        else:
            # Fallback para JSON (compatibilidade antiga)
            data = request.json
            emailContato = data.get("emailContato")
            if not emailContato:
                return jsonify({"error": "Email para contato obrigatório!"}), 400

            # Verifica se já existe cartão para este emailContato
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

# ------------------ UPDATE CARD ------------------
@routes.route("/card/<card_id>", methods=["PUT"])
def update_card(card_id):
    try:
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            form = request.form
            files = request.files

            response = cards_table.get_item(Key={"card_id": card_id})
            card = response.get("Item")
            if not card:
                return jsonify({"error": "Cartão não encontrado"}), 404

            # Atualiza os campos
            campos_editaveis = ["nome", "biografia", "empresa", "whatsapp", "emailContato", "instagram", "linkedin", "site", "chave_pix"]
            for campo in campos_editaveis:
                if campo in form:
                    card[campo] = form.get(campo)
            # Foto perfil
            if "foto_perfil" in files and files["foto_perfil"]:
                avatar = files["foto_perfil"]
                ext = avatar.filename.rsplit(".", 1)[-1].lower()
                avatar_filename = f"{card_id}_avatar.{ext}"
                avatar_path = os.path.join(UPLOAD_FOLDER, avatar_filename)
                avatar.save(avatar_path)
                card["foto_perfil"] = f"/uploads/{avatar_filename}"

            # Galeria
            galeria_filenames = []
            galeria_files = request.files.getlist("galeria")
            for idx, img in enumerate(galeria_files):
                ext = img.filename.rsplit(".", 1)[-1].lower()
                gallery_filename = f"{card_id}_gallery{idx}.{ext}"
                gallery_path = os.path.join(UPLOAD_FOLDER, gallery_filename)
                img.save(gallery_path)
                galeria_filenames.append(f"/uploads/{gallery_filename}")
            if galeria_filenames:
                card["galeria"] = galeria_filenames

            cards_table.put_item(Item=card)
            return jsonify({"message": "Cartão atualizado com sucesso"}), 200
        else:
            # Fallback para JSON (compatibilidade antiga)
            data = request.json
            response = cards_table.get_item(Key={"card_id": card_id})
            card = response.get("Item")
            if not card:
                return jsonify({"error": "Cartão não encontrado"}), 404

            campos_editaveis = ["nome", "biografia", "empresa", "whatsapp", "emailContato", "instagram", "linkedin", "site", "chave_pix", "foto_perfil", "galeria"]
            for campo in campos_editaveis:
                if campo in data:
                    card[campo] = data[campo]

            cards_table.put_item(Item=card)
            return jsonify({"message": "Cartão atualizado com sucesso"}), 200
    except Exception as e:
        print("Erro ao atualizar cartão:", e)
        return jsonify({"error": str(e)}), 500

# ------------------ DELETE CARD ------------------
@routes.route("/card/<card_id>", methods=["DELETE"])
def delete_card(card_id):
    try:
        response = cards_table.get_item(Key={"card_id": card_id})
        card = response.get("Item")
        if not card:
            return jsonify({"error": "Cartão não encontrado"}), 404

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
def token_required(f):
    from functools import wraps
    def decorator(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Token ausente'}), 401
        try:
            token = auth_header.split(' ')[1]
            jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except Exception as e:
            return jsonify({'error': str(e)}), 403
        return f(*args, **kwargs)
    return wraps(f)(decorator)

@routes.route("/segredo", methods=["GET"])
@token_required
def segredo():
    return jsonify({"mensagem": "Você tem acesso autorizado"}), 200

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
