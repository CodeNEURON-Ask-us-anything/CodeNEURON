import requests
import json

url = "http://127.0.0.1:8000/api/verify"
payload = {
    "answer": """
Here is a function that sorts an array and has an intentional error.
```python
def bad_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr)):
            if arr[i] < arr[j]:
                temp = arr[i]
                arr[i] = arr[j]
                arr[j] = temp
    return arr[len(arr) + 10]  # Intentional IndexError on line 8!
```
""",
    "source_model": "Test",
    "mode": "gemini",
    "skip_generation": True
}

try:
    print("Testing code verification features...")
    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    print(f"Raw Response: {json.dumps(data, indent=2)}")
    
    code_chunk = [c for c in data['chunks'] if c['type'] == 'code'][0]
    
    print("\n--- Error Localization ---")
    print(f"Error Line: {code_chunk['test_results'].get('error_line')}")
    print(f"Error Message: {code_chunk['test_results'].get('error_message')}")
    
    print("\n--- Time Complexity ---")
    print(f"Big-O: {code_chunk['static_analysis'].get('time_complexity_big_o')}")
    print(f"Improvement: {code_chunk['static_analysis'].get('complexity_improvement')}")
    
except Exception as e:
    print(f"Request failed: {e}")
