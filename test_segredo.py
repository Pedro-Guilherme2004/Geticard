import requests

url = "http://localhost:5000/api/segredo"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtYXVyaWNpbzEyM0BnbWFpbC5jb20iLCJleHAiOjE3NTAwMzgxNTF9.2StMfATa6lqqIv-NQpdUhinS6TWFWypOGx92JKtiDvY"

headers = {
    "Authorization": f"Bearer {token}"
}

response = requests.get(url, headers=headers)

print("Status:", response.status_code)
print("Resposta:", response.json())

