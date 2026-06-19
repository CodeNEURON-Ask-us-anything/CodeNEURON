def aggregate_claim_results(results):
    """
    Aggregates factual prose results and executable code results into a unified score.
    Prose Claims represent 80% of the overall confidence score.
    Code Chunks represent 20% of the overall confidence score.
    If any code block is marked 'UNSAFE', the overall platform verdict escalates to 'UNSAFE'.
    """
    prose_results = [r for r in results if r.get("type") == "prose" or "verdict" in r and "code" not in r]
    code_results = [r for r in results if r.get("type") == "code" or "code" in r and "verdict" in r]

    # 1. Evaluate Prose Claims
    prose_total = len(prose_results)
    prose_supported = 0
    prose_contradicted = 0
    prose_neutral = 0
    
    for r in prose_results:
        verdict = r.get("verdict", "NOT_ENOUGH_INFO")
        if verdict == "SUPPORTED":
            prose_supported += 1
        elif verdict == "CONTRADICTED":
            prose_contradicted += 1
        else:
            prose_neutral += 1

    # Factual trust score: Heavily penalize contradicted claims to ensure best credibility
    if prose_total > 0:
        prose_score = max(0.0, (prose_supported * 1.0 + prose_neutral * 0.4 - prose_contradicted * 1.0) / prose_total)
    else:
        prose_score = 1.0  # default when no prose claims

    # 2. Evaluate Code Chunks
    code_total = len(code_results)
    code_passed = 0
    code_failed = 0
    code_unsafe = 0
    
    for r in code_results:
        verdict = r.get("verdict", "PASS")
        if verdict == "PASS":
            code_passed += 1
        elif verdict == "FAIL":
            code_failed += 1
        elif verdict == "UNSAFE":
            code_unsafe += 1

    # Code correctness score: penalize failed and unsafe executions
    if code_total > 0:
        code_score = max(0.0, (code_passed * 1.0 - code_failed * 0.5 - code_unsafe * 1.0) / code_total)
    else:
        code_score = 1.0  # default when no code blocks

    # 3. Calculate Combined Weighted Score (80% Prose, 20% Code)
    if prose_total > 0 and code_total > 0:
        combined_score = round(0.8 * prose_score + 0.2 * code_score, 2)
    elif prose_total > 0:
        combined_score = round(prose_score, 2)
    elif code_total > 0:
        combined_score = round(code_score, 2)
    else:
        combined_score = 1.0

    # 4. Compute Overall Verdict
    if code_unsafe > 0:
        overall_verdict = "UNSAFE"
        summary = f"CRITICAL SECURITY HAZARD: {code_unsafe} code block(s) triggered strict platform sandbox restrictions."
    elif combined_score >= 0.8:
        overall_verdict = "TRUSTWORTHY"
        summary = "Highly reliable answer. Factual claims are search-grounded and code blocks successfully passed sandbox execution tests."
    elif combined_score >= 0.5:
        overall_verdict = "SUSPICIOUS"
        summary = "Caution advised. Several factual inconsistencies or unverified assertions were identified in the response."
    else:
        overall_verdict = "UNTRUSTWORTHY"
        summary = "Unreliable response. Factual assertions contradict verified sources, or compiled code blocks failed test suites."

    # Build descriptive breakdown details
    breakdown = f"{prose_supported} supported, {prose_contradicted} contradicted, {prose_neutral} unverified claims."
    if code_total > 0:
        breakdown += f" Code metrics: {code_passed} passed, {code_failed} failed, {code_unsafe} unsafe executions."

    return {
        "overall_verdict": overall_verdict,
        "confidence": combined_score,
        "score_percentage": int(combined_score * 100),
        "summary": summary,
        "breakdown": breakdown,
        "metrics": {
            "prose_total": prose_total,
            "prose_supported": prose_supported,
            "prose_contradicted": prose_contradicted,
            "prose_neutral": prose_neutral,
            "code_total": code_total,
            "code_passed": code_passed,
            "code_failed": code_failed,
            "code_unsafe": code_unsafe
        }
    }

