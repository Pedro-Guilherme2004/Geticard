#config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
    DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "GetiCardUsers")
    S3_BUCKET = os.getenv("S3_BUCKET", "meu-bucket-geticard")
    SECRET_KEY = os.getenv("SECRET_KEY", "sua_chave_secreta_segura")  # ✅ Correto!
