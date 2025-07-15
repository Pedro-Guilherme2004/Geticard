# services.py

import base64
import hashlib
import jwt
from flask import request, jsonify
from app.config import Config
from functools import wraps
import os
import json
from uuid import uuid4
from app.aws import users_table
from boto3.dynamodb.conditions import Attr
import boto3
import uuid

dynamodb = boto3.resource(
    'dynamodb',
    region_name=Config.AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

users_table = dynamodb.Table("GetiCardUsers")
cards_table = dynamodb.Table("Testecard")

SECRET_KEY = Config.SECRET_KEY

# Arquivo de persistência em disco
CARDS_FILE = os.path.join(os.getcwd(), 'cards.json')

# Carrega cartões do arquivo JSON
if os.path.exists(CARDS_FILE):
    with open(CARDS_FILE, 'r', encoding='utf-8') as f:
        try:
            CARDS = json.load(f)
        except json.JSONDecodeError:
            CARDS = {}
else:
    CARDS = {}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# Usuários em memória (pode evoluir para JSON também)
USERS = {}

def save_user(user_data: dict) -> None:
    key = user_data['email']
    if key in USERS:
        raise RuntimeError('Usuário já existe')
    USERS[key] = user_data

# Salva cartão em memória e em disco
def save_card(card_data: dict) -> None:
    key = card_data['card_id']
    CARDS[key] = card_data
    with open(CARDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(CARDS, f, ensure_ascii=False, indent=2)

# Obtém cartão do dicionário em memória
def get_card_local(card_id: str) -> dict:
    return CARDS.get(card_id)

# Salva imagem base64 localmente
def salvar_imagem_local(base64_data: str, card_id: str) -> str:
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    if ',' in base64_data:
        base64_data = base64_data.split(',', 1)[1]
    filename = f"{card_id}_{uuid.uuid4().hex}.png"
    path = os.path.join(uploads_dir, filename)
    with open(path, 'wb') as f:
        f.write(base64.b64decode(base64_data))
    return f"/uploads/{filename}"


# Decorator para rotas protegidas
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Token ausente'}), 401
        try:
            token = auth_header.split(' ')[1]
            jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except Exception as e:
            return jsonify({'error': str(e)}), 403
        return f(*args, **kwargs)
    return decorated

def save_user_dynamo(user_dict):
    users_table.put_item(Item=user_dict)

def get_user_dynamo(email):
    response = users_table.get_item(Key={'email': email})
    return response.get('Item')

def save_card_dynamo(card_dict):
    cards_table.put_item(Item=card_dict)

def get_card_by_user(email):
    response = cards_table.scan(FilterExpression=Attr('user_email').eq(email))
    items = response.get("Items", [])
    return items[0] if items else None


