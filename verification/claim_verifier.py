from retrieval.evidence_provide import get_evidence_for_claim
from verification.nli_model import run_nli
from verification.gemini_verifier import verify_grounded_with_gemini, verify_with_gemini
from verification.math_verifier import evaluate_math_claim


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
    Performs generic keyword/substring overlap matching when local NLI model is unavailable.
    Uses semantic heuristics to detect entailment, contradiction, or neutral stance.
    """
    claim_clean = claim.lower().replace(".", "").replace(",", "").strip()
    evidence_clean = evidence.lower().replace(".", "").replace(",", "").strip()
    
    claim_words = {w for w in claim_clean.split() if len(w) > 3}
    evidence_words = set(evidence_clean.split())
    
    if not claim_words:
        return {"label": "neutral", "confidence": 0.5}
        
    overlap = claim_words.intersection(evidence_words)
    overlap_ratio = len(overlap) / len(claim_words)
    
    # Check for negation mismatches (generic contradiction detection)
    negations = {"not", "never", "no", "isnt", "isn't", "wasnt", "wasn't", 
                 "doesn't", "doesnt", "don't", "dont", "cannot", "can't",
                 "won't", "wont", "neither", "nor", "false", "incorrect", "wrong"}
    claim_has_negation = any(n in claim_clean.split() for n in negations)
    evidence_has_negation = any(n in evidence_clean.split() for n in negations)
    
    # Generic value mismatch detection: if claim and evidence share a topic 
    # but contain different numeric values or proper nouns, likely contradiction
    import re
    claim_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', claim_clean))
    evidence_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', evidence_clean))
    has_conflicting_numbers = (
        claim_numbers and evidence_numbers 
        and overlap_ratio >= 0.4 
        and not claim_numbers.intersection(evidence_numbers)
    )
    
    if overlap_ratio >= 0.5:
        if claim_has_negation != evidence_has_negation or has_conflicting_numbers:
            return {"label": "contradiction", "confidence": round(overlap_ratio, 3)}
        return {"label": "entailment", "confidence": round(overlap_ratio, 3)}
    elif overlap_ratio >= 0.3:
        if claim_has_negation != evidence_has_negation:
            return {"label": "contradiction", "confidence": round(overlap_ratio * 0.8, 3)}
        return {"label": "entailment", "confidence": round(overlap_ratio * 0.7, 3)}
        
    return {"label": "neutral", "confidence": 0.5}


def verify_fact(claim: str, mode: str = "nli", gemini_api_key: str = None):
    """
    Main claim verification router.
    Retrieves web-grounded search evidence from Wikipedia first.
    Performs verification using either local NLI pipeline or RAG grounded Gemini 1.5 Flash.
    Falls back to Gemini direct verification when NLI is unavailable and evidence exists.
    """
    # 0. Check if it's a mathematical calculation
    math_result = evaluate_math_claim(claim)
    if math_result:
        return math_result

    # 1. Retrieval Web-Grounded Search
    evidence_list = get_evidence_for_claim(claim)

    if not evidence_list:
        # No evidence found from web search — try Gemini direct verification as fallback
        try:
            from verification.gemini_verifier import verify_with_gemini, get_gemini_model
            model = get_gemini_model(gemini_api_key)
            if model:
                direct_result = verify_with_gemini(claim, gemini_api_key)
                confidence_map = {"SUPPORTED": 0.75, "CONTRADICTED": 0.7, "NEUTRAL": 0.4}
                return {
                    "claim": claim,
                    "verdict": direct_result if direct_result in ["SUPPORTED", "CONTRADICTED"] else "NOT_ENOUGH_INFO",
                    "confidence": confidence_map.get(direct_result, 0.4),
                    "credibility_score": confidence_map.get(direct_result, 0.4),
                    "evidence": {"text": "Verified using Gemini AI knowledge base (no web evidence found).", "source": "Gemini AI"},
                    "explanation": f"No web evidence was found, but Gemini AI assessed this claim as {direct_result}."
                }
        except Exception:
            pass

        return {
            "claim": claim,
            "verdict": "NOT_ENOUGH_INFO",
            "confidence": 0.3,
            "credibility_score": 0.3,
            "evidence": None,
            "explanation": "No relevant search evidence found to verify this claim."
        }

    # 1. Cloud-based Grounded Gemini Mode
    if mode == "gemini":
        result = verify_grounded_with_gemini(claim, evidence_list, gemini_api_key)
        # Find the best evidence snippet for UI display
        best_ev = evidence_list[0] if evidence_list else None
        return {
            "claim": claim,
            "verdict": result["verdict"],
            "confidence": result["confidence"],
            "credibility_score": result["confidence"],
            "evidence": best_ev,
            "explanation": result["explanation"]
        }

    # 2. Local NLI pipeline Mode
    candidates = []
    nli_failed = False

    for ev in evidence_list:
        try:
            nli_result = run_nli(
                premise=ev["text"],
                hypothesis=claim
            )
        except Exception as e:
            # If NLI loading failed locally, mark it and try Gemini grounded verification
            print(f"Local NLI verification failed: {str(e)}.")
            nli_failed = True
            break

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

    # If NLI model is not available, use Gemini grounded verification as smart fallback
    if nli_failed:
        try:
            result = verify_grounded_with_gemini(claim, evidence_list, gemini_api_key)
            best_ev = evidence_list[0] if evidence_list else None
            return {
                "claim": claim,
                "verdict": result["verdict"],
                "confidence": result["confidence"],
                "credibility_score": result["confidence"],
                "evidence": best_ev,
                "explanation": result["explanation"] + " (NLI model unavailable, used Gemini grounded verification.)"
            }
        except Exception:
            # Final fallback: use generic keyword matching against all evidence
            print("Gemini grounded fallback also failed. Using keyword matching...")
            for ev in evidence_list:
                nli_result = direct_matching_fallback(claim, ev["text"])
                relevance = relevance_score(claim, ev["text"])
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
        "explanation": explanation
    }
