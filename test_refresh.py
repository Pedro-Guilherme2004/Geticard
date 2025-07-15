import requests

url = "http://localhost:5000/api/refresh"

data = {
    "card_id": "unico005",  # substitua pelo card_id correto
    "refresh_token": "152c6045966a56116213c5c2f822a8afb5ddbaebd3b820680fdc9672de5bced5"  # cole o recebido no login
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Resposta:", response.json())
