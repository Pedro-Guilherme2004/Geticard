#main.py
from flask import Flask, send_from_directory
from flask_cors import CORS
from app.routes import routes
import os

app = Flask(__name__)
CORS(app, origins=[
    "https://frontend-s52u.vercel.app",
    "https://frontend-8zw6.onrender.com"
], supports_credentials=True)

# Rota para servir uploads:
@app.route("/uploads/<path:filename>")
def servir_arquivo(filename):
    return send_from_directory("uploads", filename)

if __name__ == "__main__":
    app.run(debug=True)
