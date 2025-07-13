import requests

url = "http://localhost:5000/api/login"

data = {
    "card_id": "unico005",  # <- card_id usado na criação
    "email": "mauricio123@gmail.com",
    "password": "mypassword123"
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Resposta:", response.json())
