from flask import Flask, send_from_directory
from flask_cors import CORS
from app.routes import routes

app = Flask(__name__)
CORS(
    app,
    origins=["https://frontend-s52u.vercel.app"],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# REGISTRA SUAS ROTAS!
app.register_blueprint(routes)

# Rota para servir uploads:
@app.route("/uploads/<path:filename>")
def servir_arquivo(filename):
    return send_from_directory("uploads", filename)

if __name__ == "__main__":
    app.run(debug=True)

