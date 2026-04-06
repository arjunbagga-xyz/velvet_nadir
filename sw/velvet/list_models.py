import os
from google import genai

api_key = os.environ.get("VELVET_LLM_GOOGLE_API_KEY")
if not api_key:
    print("Error: VELVET_LLM_GOOGLE_API_KEY not set.")
    exit(1)

client = genai.Client(api_key=api_key)
print("Available Models:")
try:
    for model in client.models.list():
        print(f"- {model.name}")
except Exception as e:
    print(f"Error querying models: {e}")
