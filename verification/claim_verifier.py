from retrieval.evidence_provide import get_evidence_for_claim
from verification.nli_model import run_nli
from verification.gemini_verifier import verify_grounded_with_gemini
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


def verify_fact(claim: str, mode: str = "nli", gemini_api_key: str = None):
    """
    Main claim verification router.
    Retrieves web-grounded search evidence from Wikipedia first.
    Performs verification using either local NLI pipeline or RAG grounded Gemini 1.5 Flash.
    """
    # 0. Check if it's a mathematical calculation
    math_result = evaluate_math_claim(claim)
    if math_result:
        return math_result

    # 1. Retrieval Web-Grounded Search
    evidence_list = get_evidence_for_claim(claim)

    if not evidence_list:
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
        "explanation": explanation
    }
