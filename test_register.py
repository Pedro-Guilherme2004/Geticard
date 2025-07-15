import requests

url = "http://localhost:5000/api/register"

data = {
    "name": "Falt",
    "email": "mauricio123@gmail.com",
    "password": "mypassword123",
    "card_id": "unico005"
}



response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Resposta:", response.json())
