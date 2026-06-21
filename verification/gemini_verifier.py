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
        return genai.GenerativeModel("models/gemini-2.5-flash")
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
        You are an expert fact-checking AI. Your task is to verify whether the following factual claim is SUPPORTED or CONTRADICTED.
        
        Claim to verify: "{claim}"
        
        Retrieved Grounded Evidence:
        {evidence_context}
        
        Analyze the claim carefully. Use the retrieved evidence if it is relevant and accurate.
        If the evidence is irrelevant, outdated, or absent, rely entirely on your own internal knowledge to evaluate the claim:
        1. If the claim is factually true/accurate, the verdict is "SUPPORTED".
        2. If the claim is factually false/inaccurate, the verdict is "CONTRADICTED".
        3. If it is impossible to determine even with internal knowledge, the verdict is "NOT_ENOUGH_INFO".

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
            "verdict": "ERROR",
            "confidence": 0.0,
            "explanation": f"Grounded verification failed: {str(e)}"
        }

def batch_verify_grounded_with_gemini(claims_data: list, api_key: str = None):
    """
    Verifies a batch of claims grounded in their respective retrieved evidence using Gemini.
    claims_data should be a list of dicts: [{"claim": str, "evidence_list": list}, ...]
    Returns a list of structured dictionaries matching the verification schema.
    """
    if not claims_data:
        return []
        
    try:
        model = get_gemini_model(api_key)
        if not model:
            return [{
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 0.3,
                "explanation": "Gemini API configuration failed."
            } for _ in claims_data]

        # Format retrieved evidence into string context
        batch_prompt = "You are an expert fact-checking AI. Your task is to verify a batch of factual claims.\n\n"
        
        for i, data in enumerate(claims_data):
            claim = data["claim"]
            evidence_list = data.get("evidence_list", [])
            evidence_context = ""
            if evidence_list:
                for idx, ev in enumerate(evidence_list):
                    evidence_context += f"Evidence [{idx+1}]: {ev['text']} (Source: {ev['source']})\n"
            else:
                evidence_context = "No direct evidence retrieved."
                
            batch_prompt += f"--- CLAIM {i} ---\n"
            batch_prompt += f"Claim to verify: \"{claim}\"\n"
            batch_prompt += f"Retrieved Grounded Evidence:\n{evidence_context}\n\n"

        batch_prompt += """
        Analyze each claim carefully. Use the retrieved evidence if it is relevant and accurate.
        If the evidence is irrelevant, outdated, or absent, rely entirely on your own internal knowledge to evaluate the claim:
        1. If the claim is factually true/accurate, the verdict is "SUPPORTED".
        2. If the claim is factually false/inaccurate, the verdict is "CONTRADICTED".
        3. If it is impossible to determine even with internal knowledge, the verdict is "NOT_ENOUGH_INFO".

        Respond ONLY in JSON format. It MUST be a JSON array of objects, where the array length exactly matches the number of claims.
        Each object must match this schema exactly:
        {
            "claim_index": <integer index of the claim, starting from 0>,
            "verdict": "SUPPORTED" or "CONTRADICTED" or "NOT_ENOUGH_INFO",
            "confidence": <float between 0.0 and 1.0 representing your confidence in this decision>,
            "explanation": "<a short, single-sentence explanation of why the verdict was chosen based on the evidence>"
        }

        Do NOT include any codeblock backticks or formatting. Just output raw JSON array.
        """
        
        response = model.generate_content(batch_prompt)
        content = response.text.strip()
        
        # Sanitize markdown codeblock wrappers if returned by the LLM
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()

        try:
            results = json.loads(content)
            if not isinstance(results, list):
                raise ValueError("Expected a JSON array")
                
            # Create a mapped response list
            final_results = []
            for i in range(len(claims_data)):
                # Find matching result by index, or fallback
                res = next((r for r in results if r.get("claim_index") == i), None)
                if res:
                    verdict = res.get("verdict", "NOT_ENOUGH_INFO").upper()
                    if verdict not in ["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]:
                        verdict = "NOT_ENOUGH_INFO"
                    final_results.append({
                        "verdict": verdict,
                        "confidence": float(res.get("confidence", 0.5)),
                        "explanation": res.get("explanation", "Verified using grounded LLM assessment.")
                    })
                else:
                    final_results.append({
                        "verdict": "NOT_ENOUGH_INFO",
                        "confidence": 0.3,
                        "explanation": "Model omitted this claim from the batch response."
                    })
            return final_results
        except Exception as parse_e:
            print(f"JSON Parse Error in batch verification: {str(parse_e)}")
            # Fallback for all
            return [{
                "verdict": "NOT_ENOUGH_INFO",
                "confidence": 0.5,
                "explanation": "Verified using raw text analysis."
            } for _ in claims_data]
            
    except Exception as e:
        print(f"Grounded Gemini batch verification error: {str(e)}")
        return [{
            "verdict": "ERROR",
            "confidence": 0.0,
            "explanation": f"Grounded verification failed: {str(e)}"
        } for _ in claims_data]


