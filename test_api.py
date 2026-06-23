import requests
import json

url = "http://127.0.0.1:8000/api/verify"
payload = {
    "answer": "Python was created by Guido van Rossum and was first released in 1991. The moon is made of green cheese.",
    "source_model": "Custom External Model",
    "mode": "nli",
    "skip_generation": True
}

print(f"Sending factual answer to {url} for validation...")
print(f"Text being validated:\n\"{payload['answer']}\"\n")

try:
    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    
    print("=== VALIDATION RESULTS ===")
    print(f"Overall Verdict: {data['metrics']['overall_verdict']}")
    print(f"Overall Score / Confidence: {data['metrics']['confidence'] * 100}%\n")
    
    print("=== CLAIM BREAKDOWN ===")
    for idx, chunk in enumerate(data['chunks']):
        print(f"Claim {idx + 1}: {chunk['content']}")
        print(f"  Verdict: {chunk['verdict']}")
        print(f"  Credibility Score: {chunk.get('credibility_score', 'N/A')}")
        if chunk.get('evidence'):
            print(f"  Evidence Used: {chunk['evidence']['source']}")
        print(f"  Explanation: {chunk.get('explanation', '')}\n")
        
except Exception as e:
    print(f"Error: {e}")
