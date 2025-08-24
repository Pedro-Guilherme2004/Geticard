# app/storage.py
import os, uuid
import boto3

_s3 = boto3.client(
    "s3",
    region_name=os.environ["AWS_REGION"],
    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)
_BUCKET = os.environ["S3_BUCKET"]
_REGION = os.environ["AWS_REGION"]

def s3_url(key: str) -> str:
    return f"https://{_BUCKET}.s3.{_REGION}.amazonaws.com/{key}"

def upload_image(file_storage, key_prefix="cards"):
    ext = (file_storage.filename or "bin").rsplit(".", 1)[-1].lower()
    key = f"{key_prefix}/{uuid.uuid4().hex}.{ext}"
    _s3.upload_fileobj(
        file_storage, _BUCKET, key,
        ExtraArgs={"ACL": "public-read", "ContentType": file_storage.mimetype}
    )
    return s3_url(key)

def delete_image_by_url(url: str):
    # opcional: remover do bucket quando deletar o cartão
    try:
        base = f"https://{_BUCKET}.s3.{_REGION}.amazonaws.com/"
        if url.startswith(base):
            key = url[len(base):]
            _s3.delete_object(Bucket=_BUCKET, Key=key)
    except Exception:
        pass