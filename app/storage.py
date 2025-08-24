# app/storage.py
import os, uuid
from werkzeug.utils import secure_filename

_BUCKET = os.getenv("S3_BUCKET")
_REGION = os.getenv("AWS_REGION") or "us-east-1"
_AK = os.getenv("AWS_ACCESS_KEY_ID")
_SK = os.getenv("AWS_SECRET_ACCESS_KEY")
_ENDPOINT = os.getenv("S3_ENDPOINT_URL")  # opcional
_USE_S3 = bool(_BUCKET and _AK and _SK)

if _USE_S3:
    import boto3
    _s3 = boto3.client(
        "s3",
        region_name=_REGION,
        aws_access_key_id=_AK,
        aws_secret_access_key=_SK,
        endpoint_url=_ENDPOINT if _ENDPOINT else None,
    )

_UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), "..", "uploads")

def _local_save(file, key_prefix="uploads"):
    os.makedirs(_UPLOAD_ROOT, exist_ok=True)
    fname = f"{uuid.uuid4().hex}-{secure_filename(file.filename or 'file.bin')}"
    path = os.path.join(_UPLOAD_ROOT, fname)
    file.save(path)
    return f"/uploads/{fname}"

def upload_image(file, key_prefix="uploads"):
    if not file:
        return ""
    if _USE_S3:
        key = f"{key_prefix.strip('/')}/{uuid.uuid4().hex}-{secure_filename(file.filename or 'file.bin')}"
        _s3.upload_fileobj(
            file, _BUCKET, key,
            ExtraArgs={"ACL": "public-read", "ContentType": file.mimetype or "application/octet-stream"}
        )
        host = f"https://{_BUCKET}.s3.{_REGION}.amazonaws.com"
        if _ENDPOINT and "amazonaws.com" not in _ENDPOINT:
            # provedor S3 compatível (ex.: R2/Wasabi)
            host = _ENDPOINT.rstrip("/")
            # tenta usar estilo virtual-host se possível
            if _BUCKET not in host:
                # path-style: https://endpoint/bucket/key
                return f"{host}/{_BUCKET}/{key}"
        return f"{host}/{key}"
    # fallback local
    return _local_save(file, key_prefix)

def delete_image_by_url(url: str):
    if not url or not _USE_S3:
        return
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        key = p.path.lstrip("/")
        # Se vier em formato path-style: /bucket/key
        if key.split("/")[0] == _BUCKET:
            key = "/".join(key.split("/")[1:])
        _s3.delete_object(Bucket=_BUCKET, Key=key)
    except Exception:
        # não quebra a app por erro de limpeza
        pass
