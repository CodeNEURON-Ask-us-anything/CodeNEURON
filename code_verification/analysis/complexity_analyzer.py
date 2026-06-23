import re
import json
from verification.gemini_verifier import get_gemini_model

def analyze_code_complexity(code_text: str, api_key: str = None) -> dict:
    """
    Uses Gemini to analyze code and provide Time Complexity, Space Complexity, 
    and an Optimized Solution.
    Returns a dictionary with these keys.
    """
    default_response = {
        "time_complexity": "N/A",
        "space_complexity": "N/A",
        "optimized_solution": "Optimization requires Gemini API Key."
    }

    if not api_key:
        return default_response

    try:
        model = get_gemini_model(api_key)
        if not model:
            return default_response

        prompt = f"""
        Analyze the following Python code and provide its Time Complexity (in Big-O notation),
        Space Complexity (in Big-O notation), and a more optimized version of the code if possible.
        If the code is already optimal, just return the original code but clean it up.
        
        Respond ONLY with a valid JSON object matching this schema exactly, and absolutely no markdown wrapping:
        {{
            "time_complexity": "O(...)",
            "space_complexity": "O(...)",
            "optimized_solution": "def optimized()..."
        }}

        Code:
        {code_text}
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up any potential markdown code blocks
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n", "", text)
            text = re.sub(r"\n```$", "", text)
            
        result = json.loads(text.strip())
        return result
    except Exception as e:
        print(f"Complexity analysis failed: {str(e)}")
        return default_response
