import os
import json
import re

# Fallback default API key provided in the starter template
DEFAULT_API_KEY = "AIzaSyDVpdeXaCrNXXFSHuxbR_H3ZOVfNkCUk9Q"

def get_gemini_model(api_key: str = None):
    """
    Configures and returns a Gemini model instance.
    Uses the provided key, environment variable, or default key in order.
    """
    import google.generativeai as genai
    
    key = api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_API_KEY
    try:
        genai.configure(api_key=key)
        return genai.GenerativeModel("models/gemini-1.5-flash")
    except Exception as e:
        print(f"Error configuring Google Generative AI: {str(e)}")
        return None


def verify_with_gemini(claim: str, api_key: str = None):
    """
    Verifies a claim directly using Gemini 1.5 Flash.
    """
    try:
        model = get_gemini_model(api_key)
        if not model:
            return "NEUTRAL"
            
        prompt = f"""
        Verify the following factual claim.

        Claim: "{claim}"

        Respond with ONLY one word:
        SUPPORTED, CONTRADICTED, or NEUTRAL.
        """
        response = model.generate_content(prompt)
        verdict = response.text.strip().upper()
        
        # Clean up any potential markdown or punctuation returned by LLM
        for opt in ["SUPPORTED", "CONTRADICTED", "NEUTRAL"]:
            if opt in verdict:
                return opt
        return "NEUTRAL"
    except Exception as e:
        print(f"Gemini verification error: {str(e)}")
        return "NEUTRAL"


def verify_grounded_with_gemini(claim: str, evidence_list: list, api_key: str = None):
    """
    Verifies a claim grounded in retrieved evidence using Gemini.
    Returns a structured dictionary matching the verification schema.
    """
    try:
        model = get_gemini_model(api_key)
        if not model:
            return {
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 0.3,
                "explanation": "Gemini API configuration failed."
            }

        # Format retrieved evidence into string context
        evidence_context = ""
        if evidence_list:
            for idx, ev in enumerate(evidence_list):
                evidence_context += f"Evidence [{idx+1}]: {ev['text']} (Source: {ev['source']})\n"
        else:
            evidence_context = "No direct evidence retrieved."

        prompt = f"""
        You are an expert fact-checking AI. Your task is to verify whether the following factual claim is supported or contradicted by the retrieved evidence.
        
        Claim to verify: "{claim}"
        
        Retrieved Grounded Evidence:
        {evidence_context}
        
        Analyze the claim carefully against the evidence:
        1. If the evidence directly supports/confirms the claim, the verdict is "SUPPORTED".
        2. If the evidence contradicts/refutes the claim, the verdict is "CONTRADICTED".
        3. If the evidence does not contain enough information to prove or disprove the claim, the verdict is "NOT_ENOUGH_INFO".

        Respond ONLY in JSON format matching this schema exactly:
        {{
            "verdict": "SUPPORTED" or "CONTRADICTED" or "NOT_ENOUGH_INFO",
            "confidence": <float between 0.0 and 1.0 representing your confidence in this decision>,
            "explanation": "<a short, single-sentence explanation of why the verdict was chosen based on the evidence>"
        }}

        Do NOT include any codeblock backticks or formatting. Just output raw JSON.
        """
        
        response = model.generate_content(prompt)
        content = response.text.strip()
        
        # Sanitize markdown codeblock wrappers if returned by the LLM
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()

        try:
            result = json.loads(content)
            # Map neutral/not_enough_info keys robustly
            verdict = result.get("verdict", "NOT_ENOUGH_INFO").upper()
            if verdict == "NEUTRAL" or verdict not in ["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]:
                verdict = "NOT_ENOUGH_INFO"
                
            return {
                "verdict": verdict,
                "confidence": float(result.get("confidence", 0.5)),
                "explanation": result.get("explanation", "Verified using grounded LLM assessment.")
            }
        except Exception:
            # Simple regex search in case of JSON parse failure
            verdict = "NOT_ENOUGH_INFO"
            if "SUPPORTED" in content.upper():
                verdict = "SUPPORTED"
            elif "CONTRADICTED" in content.upper():
                verdict = "CONTRADICTED"
            return {
                "verdict": verdict,
                "confidence": 0.5,
                "explanation": "Verified using raw text analysis."
            }
    except Exception as e:
        print(f"Grounded Gemini verification error: {str(e)}")
        return {
            "verdict": "NOT_ENOUGH_INFO",
            "confidence": 0.3,
            "explanation": f"Grounded verification failed: {str(e)}"
        }

