import json
import requests

payload = {
    "answer": "Who is the CM of TN?",
    "source_model": "Multi-Agent Consensus (Gemini, Groq, OpenAI)",
    "mode": "gemini",
    "input_type": "prose"
}

resp = requests.post("http://127.0.0.1:8000/api/verify", json=payload)
print(resp.status_code)
print(resp.text)
