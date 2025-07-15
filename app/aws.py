# app/aws.py
import boto3
import os
from app.config import Config

dynamodb = boto3.resource(
    'dynamodb',
    region_name=Config.AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

users_table = dynamodb.Table("GetiCardUsers")  # ou Testecard se for cartão
cards_table = dynamodb.Table("Testecard")
