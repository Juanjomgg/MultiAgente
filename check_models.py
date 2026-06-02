# check_models.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ABACUS_API_KEY")

response = requests.get(
    "https://routellm.abacus.ai/v1/models",
    headers={"Authorization": f"Bearer {API_KEY}"}
)

print(response.status_code)
data = response.json()

for model in data.get("data", []):
    print(model["id"])