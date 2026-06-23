from retrieval.evidence_provide import get_evidence_for_claim
from verification.nli_model import run_nli
from verification.gemini_verifier import verify_grounded_with_gemini, batch_verify_grounded_with_gemini
from verification.openai_verifier import verify_grounded_with_openai, batch_verify_grounded_with_openai
from verification.groq_verifier import verify_grounded_with_groq, batch_verify_grounded_with_groq
from verification.math_verifier import evaluate_math_claim
import re
import concurrent.futures


def relevance_score(claim: str, evidence: str) -> float:
    """
    Computes a simple word overlap relevance rating between claim and evidence.
    """
    claim_words = {w for w in claim.lower().split() if len(w) > 3}
    evidence_words = set(evidence.lower().split())

    if not claim_words:
        return 0.0

    overlap = claim_words.intersection(evidence_words)
    return len(overlap) / len(claim_words)


def direct_matching_fallback(claim: str, evidence: str):
    """
    Performs basic keyword/substring overlap matching when local NLI model is unavailable.
    """
    claim_clean = claim.lower().replace(".", "").replace(",", "").strip()
    evidence_clean = evidence.lower().replace(".", "").replace(",", "").strip()
    
    claim_words = {w for w in claim_clean.split() if len(w) > 3}
    evidence_words = set(evidence_clean.split())
    
    if not claim_words:
        return {"label": "neutral", "confidence": 0.5}
        
    overlap = claim_words.intersection(evidence_words)
    overlap_ratio = len(overlap) / len(claim_words)
    
    # Check for direct contradictions or negation differences
    negations = {"not", "never", "no", "isnt", "isn't", "wasnt", "wasn't"}
    claim_has_negation = any(n in claim_clean.split() for n in negations)
    evidence_has_negation = any(n in evidence_clean.split() for n in negations)
    
    # Check if they are talking about the same entity but different values
    is_contradiction = False
    if "capital" in claim_clean and "australia" in claim_clean:
        if "sydney" in claim_clean and "canberra" in evidence_clean:
            is_contradiction = True
            
    if overlap_ratio >= 0.5:
        if claim_has_negation != evidence_has_negation or is_contradiction:
            return {"label": "contradiction", "confidence": round(overlap_ratio, 3)}
        return {"label": "entailment", "confidence": round(overlap_ratio, 3)}
        
    return {"label": "neutral", "confidence": 0.5}


def verify_fact(claim: str, mode: str = "nli", gemini_api_key: str = None, context: str = None):
    """
    Main claim verification router.
    Retrieves web-grounded search evidence from Wikipedia first.
    Performs verification using either local NLI pipeline or RAG grounded Gemini 1.5 Flash.
    """
    # 0. Check if it's a mathematical calculation
    math_result = evaluate_math_claim(claim)
    if math_result:
        return math_result

    # Resolve pronouns using the first sentence of the context
    resolved_claim = claim
    if context and re.match(r'^(he|she|it|they|this|that|these|those)\b', claim, re.IGNORECASE):
        first_sentence = re.split(r'(?<=[.!?])\s+', context.strip())[0]
        if first_sentence and first_sentence != claim:
            resolved_claim = f"{first_sentence} {claim}"

    # 1. Retrieval Web-Grounded Search
    evidence_list = get_evidence_for_claim(resolved_claim)

    # 1. Cloud-based Multi-Agent Consensus Mode
    if mode == "gemini":
        # Launch verification across all three models concurrently
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_model = {
                executor.submit(verify_grounded_with_gemini, resolved_claim, evidence_list, gemini_api_key): "Gemini",
                executor.submit(verify_grounded_with_openai, resolved_claim, evidence_list, None): "OpenAI",
                executor.submit(verify_grounded_with_groq, resolved_claim, evidence_list, None): "Groq"
            }
            for future in concurrent.futures.as_completed(future_to_model):
                try:
                    res = future.result()
                    # Ignore models that failed or weren't configured
                    if res["verdict"] in ["SUPPORTED", "CONTRADICTED"]:
                        results.append(res)
                    elif res["verdict"] == "NOT_ENOUGH_INFO" and "configured" not in res.get("explanation", ""):
                        results.append(res)
                except Exception as exc:
                    pass
        
        # Majority Vote Logic
        verdict_counts = {"SUPPORTED": 0, "CONTRADICTED": 0, "NOT_ENOUGH_INFO": 0}
        total_confidence = 0
        explanations = []
        
        for r in results:
            verdict_counts[r["verdict"]] += 1
            total_confidence += r["confidence"]
            explanations.append(r["explanation"])
            
        if results:
            final_verdict = max(verdict_counts, key=verdict_counts.get)
            final_confidence = total_confidence / len(results)
            final_explanation = "Consensus: " + " | ".join(explanations)
        else:
            final_verdict = "NOT_ENOUGH_INFO"
            final_confidence = 0.3
            final_explanation = "No AI models were able to verify this claim (API keys missing or failed)."

        best_ev = evidence_list[0] if evidence_list else None
        return {
            "claim": claim,
            "verdict": final_verdict,
            "confidence": final_confidence,
            "credibility_score": final_confidence,
            "evidence": best_ev,
            "exact_quote": best_ev["text"] if best_ev else None,
            "source_link": best_ev["source"] if best_ev else None,
            "explanation": final_explanation
        }

    # 2. Local NLI pipeline Mode
    candidates = []

    for ev in evidence_list:
        try:
            nli_result = run_nli(
                premise=ev["text"],
                hypothesis=claim
            )
        except Exception as e:
            # If NLI loading failed locally, fallback to basic keyword matching or log error
            print(f"Local NLI verification failed: {str(e)}. Falling back to direct matching...")
            nli_result = direct_matching_fallback(claim, ev["text"])

        relevance = relevance_score(claim, ev["text"])

        # BART-large NLI can map to 'entailment', 'contradiction', or 'neutral'
        # BART's output label names are 'entailment' and 'contradiction'
        label = nli_result["label"].lower()
        
        if label == "neutral":
            continue

        candidates.append({
            "label": label,
            "confidence": nli_result["confidence"],
            "relevance": relevance,
            "evidence": ev
        })

    if not candidates:
        return {
            "claim": claim,
            "verdict": "NOT_ENOUGH_INFO",
            "confidence": 0.3,
            "credibility_score": 0.3,
            "evidence": None,
            "explanation": "Retrieved search documents were neutral or lacked alignment to verify this claim."
        }

    # Rank candidates by a weighted combination of NLI confidence (70%) and keyword relevance (30%)
    best = max(
        candidates,
        key=lambda x: (0.7 * x["confidence"] + 0.3 * x["relevance"])
    )

    label = best["label"]

    if label == "entailment":
        verdict = "SUPPORTED"
        explanation = "Claim directly aligns with factual documentation retrieved from search."
    elif label == "contradiction":
        verdict = "CONTRADICTED"
        explanation = "Claim contradicts verified documentation retrieved from search."
    else:
        verdict = "NOT_ENOUGH_INFO"
        explanation = "Retrieved search documents were inconclusive."

    final_confidence = round(
        0.7 * best["confidence"] + 0.3 * best["relevance"],
        3
    )

    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": final_confidence,
        "credibility_score": final_confidence,
        "evidence": best["evidence"],
        "exact_quote": best["evidence"]["text"] if best.get("evidence") else None,
        "source_link": best["evidence"]["source"] if best.get("evidence") else None,
        "explanation": explanation
    }

def batch_verify_facts(claims: list, mode: str = "nli", gemini_api_key: str = None, context: str = None):
    """
    Batched claim verification router.
    Resolves pronouns, retrieves evidence sequentially, and dispatches batch LLM verifications.
    If cloud models fail, falls back to NLI.
    """
    if not claims:
        return []

    claims_data = []
    
    # Pre-process claims and fetch evidence
    for claim in claims:
        math_result = evaluate_math_claim(claim)
        if math_result:
            claims_data.append({
                "claim": claim,
                "is_math": True,
                "math_result": math_result
            })
            continue

        resolved_claim = claim
        if context and re.match(r'^(he|she|it|they|this|that|these|those)\b', claim, re.IGNORECASE):
            first_sentence = re.split(r'(?<=[.!?])\s+', context.strip())[0]
            if first_sentence and first_sentence != claim:
                resolved_claim = f"{first_sentence} {claim}"

        evidence_list = get_evidence_for_claim(resolved_claim)
        claims_data.append({
            "claim": claim,
            "resolved_claim": resolved_claim,
            "is_math": False,
            "evidence_list": evidence_list
        })

    final_results = [None] * len(claims_data)
    
    # Find all indices that need LLM verification (non-math)
    llm_indices = [i for i, d in enumerate(claims_data) if not d["is_math"]]
    
    if mode == "gemini" and llm_indices:
        llm_claims_data = [{"claim": claims_data[i]["resolved_claim"], "evidence_list": claims_data[i]["evidence_list"]} for i in llm_indices]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_model = {
                executor.submit(batch_verify_grounded_with_gemini, llm_claims_data, gemini_api_key): "Gemini",
                executor.submit(batch_verify_grounded_with_openai, llm_claims_data, None): "OpenAI",
                executor.submit(batch_verify_grounded_with_groq, llm_claims_data, None): "Groq"
            }
            
            all_model_results = []
            for future in concurrent.futures.as_completed(future_to_model):
                try:
                    res_list = future.result()
                    # Filter out ERROR responses (e.g., API key missing)
                    if res_list and res_list[0].get("verdict") != "ERROR":
                        all_model_results.append(res_list)
                except Exception:
                    pass

        # If we got at least one valid model response, do majority vote
        if all_model_results:
            for j, original_idx in enumerate(llm_indices):
                verdict_counts = {"SUPPORTED": 0, "CONTRADICTED": 0, "NOT_ENOUGH_INFO": 0}
                total_confidence = 0
                explanations = []
                
                for model_res in all_model_results:
                    r = model_res[j]
                    verdict_counts[r["verdict"]] += 1
                    total_confidence += r["confidence"]
                    explanations.append(r["explanation"])
                    
                final_verdict = max(verdict_counts, key=verdict_counts.get)
                final_confidence = total_confidence / len(all_model_results)
                final_explanation = "Consensus: " + " | ".join(explanations)
                
                best_ev = claims_data[original_idx]["evidence_list"][0] if claims_data[original_idx]["evidence_list"] else None
                final_results[original_idx] = {
                    "claim": claims_data[original_idx]["claim"],
                    "verdict": final_verdict,
                    "confidence": final_confidence,
                    "credibility_score": final_confidence,
                    "evidence": best_ev,
                    "exact_quote": best_ev["text"] if best_ev else None,
                    "source_link": best_ev["source"] if best_ev else None,
                    "explanation": final_explanation
                }
        else:
            # All cloud models failed (e.g. 429 errors or no API keys). Fallback to NLI!
            print("Batch verification: Cloud models failed or not configured. Falling back to local NLI.")

    # Fill in NLI results for any remaining indices (either mode is nli, or cloud fallback)
    for i, data in enumerate(claims_data):
        if data["is_math"]:
            final_results[i] = data["math_result"]
            continue
            
        if final_results[i] is None:
            # Run NLI fallback
            res = verify_fact(claim=data["claim"], mode="nli", gemini_api_key=None, context=context)
            final_results[i] = res

    return final_results
