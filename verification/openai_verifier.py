import os
import json
import re

def get_openai_client(api_key: str = None):
    try:
        from openai import OpenAI
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key: return None
        return OpenAI(api_key=key)
    except Exception:
        return None

def verify_grounded_with_openai(claim: str, evidence_list: list, api_key: str = None):
    try:
        client = get_openai_client(api_key)
        if not client:
            return {"verdict": "NOT_ENOUGH_INFO", "confidence": 0.3, "explanation": "OpenAI API not configured."}

        evidence_context = ""
        if evidence_list:
            for idx, ev in enumerate(evidence_list):
                evidence_context += f"Evidence [{idx+1}]: {ev['text']} (Source: {ev['source']})\n"
        else:
            evidence_context = "No direct evidence retrieved."

        prompt = f"""You are an expert fact-checking AI. 
Claim: "{claim}"
Evidence:
{evidence_context}

Analyze the claim. Use the evidence if it is relevant and accurate. If the evidence is irrelevant, outdated, or absent, rely entirely on your internal knowledge to evaluate the claim.
If the claim is factually true, output SUPPORTED. If it is factually false, output CONTRADICTED. If impossible to determine, output NOT_ENOUGH_INFO.
Respond ONLY in JSON format:
{{
    "verdict": "SUPPORTED" or "CONTRADICTED" or "NOT_ENOUGH_INFO",
    "confidence": <float 0.0-1.0>,
    "explanation": "<short single sentence>"
}}"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()

        result = json.loads(content)
        verdict = result.get("verdict", "NOT_ENOUGH_INFO").upper()
        if verdict not in ["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]:
            verdict = "NOT_ENOUGH_INFO"

        return {
            "verdict": verdict,
            "confidence": float(result.get("confidence", 0.5)),
            "explanation": result.get("explanation", "OpenAI assessment.")
        }
    except Exception as e:
        return {"verdict": "ERROR", "confidence": 0.0, "explanation": f"OpenAI failed: {str(e)}"}

def batch_verify_grounded_with_openai(claims_data: list, api_key: str = None):
    if not claims_data: return []
    try:
        client = get_openai_client(api_key)
        if not client:
            return [{"verdict": "NOT_ENOUGH_INFO", "confidence": 0.3, "explanation": "OpenAI API not configured."} for _ in claims_data]

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
                
            batch_prompt += f"--- CLAIM {i} ---\nClaim to verify: \"{claim}\"\nEvidence:\n{evidence_context}\n\n"

        batch_prompt += """Analyze each claim carefully. Use the evidence if it is relevant and accurate. If the evidence is irrelevant, outdated, or absent, rely entirely on your internal knowledge.
If the claim is factually true, output SUPPORTED. If it is factually false, output CONTRADICTED. If impossible to determine, output NOT_ENOUGH_INFO.
Respond ONLY in JSON format as an array of objects:
[
  {
    "claim_index": <integer index of the claim>,
    "verdict": "SUPPORTED" or "CONTRADICTED" or "NOT_ENOUGH_INFO",
    "confidence": <float 0.0-1.0>,
    "explanation": "<short single sentence>"
  }
]"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": batch_prompt}],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n", "", content)
            content = re.sub(r"\n```$", "", content)
            content = content.strip()

        results = json.loads(content)
        final_results = []
        for i in range(len(claims_data)):
            res = next((r for r in results if r.get("claim_index") == i), None)
            if res:
                verdict = res.get("verdict", "NOT_ENOUGH_INFO").upper()
                if verdict not in ["SUPPORTED", "CONTRADICTED", "NOT_ENOUGH_INFO"]:
                    verdict = "NOT_ENOUGH_INFO"
                final_results.append({
                    "verdict": verdict,
                    "confidence": float(res.get("confidence", 0.5)),
                    "explanation": res.get("explanation", "OpenAI assessment.")
                })
            else:
                final_results.append({"verdict": "NOT_ENOUGH_INFO", "confidence": 0.3, "explanation": "Omitted from response."})
        return final_results
    except Exception as e:
        return [{"verdict": "ERROR", "confidence": 0.0, "explanation": f"OpenAI failed: {str(e)}"} for _ in claims_data]
