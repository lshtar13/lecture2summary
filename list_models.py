import os
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

print("Listing models...")
try:
    for model in client.models.list():
        print(f"Model ID: {model.name}, Supported Actions: {model.supported_actions}")
except Exception as e:
    print(f"Error: {e}")
