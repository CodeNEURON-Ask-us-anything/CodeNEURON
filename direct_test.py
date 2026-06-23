from code_verification.router import verify_code_chunk

chunk = {
    "type": "code",
    "language": "python",
    "content": """
def bad_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr)):
            if arr[i] < arr[j]:
                temp = arr[i]
                arr[i] = arr[j]
                arr[j] = temp
    return arr[len(arr) + 10]  # Intentional IndexError on line 8!
    """
}

# we will force use_gemini = False to test fallback, or True to test gemini
# but without api key gemini fails gracefully anyway.
res = verify_code_chunk(chunk, use_gemini=False, api_key=None)

print(f"Error Line: {res['test_results'].get('error_line')}")
print(f"Big-O: {res['static_analysis'].get('time_complexity_big_o')}")
print(f"Improvement: {res['static_analysis'].get('complexity_improvement')}")
