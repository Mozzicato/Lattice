import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    load_dotenv(".env")

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Model: {m.name}")
            print(f"  Display name: {m.display_name}")
            print(f"  Input token limit: {m.input_token_limit}")
            print(f"  Output token limit: {m.output_token_limit}")
            print("-" * 20)
except Exception as e:
    print(f"Error: {e}")
