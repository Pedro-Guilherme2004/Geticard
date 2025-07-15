#main.py
from flask import Flask, send_from_directory
from flask_cors import CORS
from app.routes import routes
import os

app = Flask(__name__)
CORS(app)
app.register_blueprint(routes, url_prefix="/api")

# Rota para servir uploads:
@app.route("/uploads/<path:filename>")
def servir_arquivo(filename):
    return send_from_directory("uploads", filename)

if __name__ == "__main__":
    app.run(debug=True)
