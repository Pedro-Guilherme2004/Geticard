# app.py
from flask import Flask, send_from_directory
from flask_cors import CORS
import re

app = Flask(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://geticard.com",
    "https://www.geticard.com",
    "https://frontend-s52u.vercel.app",         # produção (se tiver)
    re.compile(r"^https://.*\.vercel\.app$"),   # previews do Vercel
]

CORS(
    app,
    resources={
        r"/*": {
            "origins": ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            # deixe False se você NÃO usa cookies/sessão no navegador
            "supports_credentials": False,
            "max_age": 86400,   # cache do preflight (opcional)
        }
    },
)

# REGISTRA SUAS ROTAS
from app.routes import routes
app.register_blueprint(routes)

# Servir uploads (mantém como está)
@app.route("/uploads/<path:filename>")
def servir_arquivo(filename):
    return send_from_directory("uploads", filename)

if __name__ == "__main__":
    app.run(debug=True)


