import boto3
import os

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("AWS_S3_BUCKET")

s3 = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

def upload_to_s3(file_obj, filename, content_type):
    try:
        s3.upload_fileobj(
            file_obj,
            S3_BUCKET,
            filename,
            ExtraArgs={'ContentType': content_type, 'ACL': 'public-read'}
        )
        url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
        return url
    except Exception as e:
        print("Erro no upload para S3:", e)
        return None
