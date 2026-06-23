import os
import json
import re
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ingestion.ingest import ingest_answer
from chunking.chunker import chunk_answer, extract_claims
from verification.claim_verifier import verify_fact
from code_verification.router import verify_code_chunk
from aggregation.answer_aggregator import aggregate_claim_results
from verification.math_verifier import evaluate_math_expression
from verification.gemini_verifier import get_gemini_model

app = FastAPI(title="CodeNeuron - AI Answer Verification & Validation Platform")

# Workspace database paths for history logging
HISTORY_DB_PATH = "verification_history.json"

# Base Request Schema
class VerificationRequest(BaseModel):
    answer: str
    source_model: str = "Unknown"
    mode: str = "nli"  # "nli" or "gemini"
    gemini_api_key: str = None
    skip_generation: bool = False

# Legacy Request Schema
class AnswerInput(BaseModel):
    answer: str

# Legacy Response Schema
class ClaimsOutput(BaseModel):
    claims: list[str]


def load_history():
    """Loads historical reports from the local JSON file database."""
    if not os.path.exists(HISTORY_DB_PATH):
        return []
    try:
        with open(HISTORY_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(entry):
    """Appends a new verification report entry to the historical database."""
    history = load_history()
    # Limit database items to last 20 queries to prevent file bloating
    history = [entry] + history[:19]
    try:
        with open(HISTORY_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
    except Exception as e:
        print(f"Error saving historical log: {str(e)}")


def auto_generate_answer(text: str, mode: str = "nli", api_key: str = None) -> tuple[str, bool]:
    """
    Checks if the user's input is a question, math prompt, or general request.
    If so, generates/solves the answer and returns (generated_answer, True).
    Otherwise, returns (original_text, False).
    Works for ANY factual question by leveraging Gemini + web search evidence.
    """
    clean_text = text.strip()
    
    # 1. Detect if it's a mathematical expression
    math_eval = evaluate_math_expression(clean_text)
    if math_eval:
        return math_eval["equation"], True
        
    # 2. Check if it looks like a question or a general prompt
    prompt_verbs = (
        "what", "who", "where", "when", "why", "how", "is", "are", "can",
        "calculate", "solve", "evaluate", "give", "tell", "please",
        "write", "explain", "create", "list", "show", "generate", "code",
        "run", "describe", "compare", "define", "implement", "make", "find",
        "which", "does", "do", "could", "should", "would", "will", "was",
        "were", "has", "have", "had", "name", "state", "mention"
    )
    is_q = (
        clean_text.endswith("?") or 
        clean_text.lower().startswith(prompt_verbs)
    )
    
    if is_q:
        # If the user is making a claim (contains '='), don't treat it as a question
        if '=' in clean_text:
            return text, False

        # Check if there is an arithmetic expression inside the question
        math_match = re.search(r'([a-zA-Z\d\.\s\+\-\*\/\^\(\)]+)', clean_text)
        if math_match:
            expr = math_match.group(1).strip()
            if any(char.isdigit() for char in expr) or any(func in expr.lower() for func in ['pi', 'e']):
                for prefix in ["what is", "calculate", "solve", "evaluate", "find"]:
                    if expr.lower().startswith(prefix):
                        expr = expr[len(prefix):].strip()
                math_eval = evaluate_math_expression(expr)
                if math_eval:
                    return math_eval['equation'], True

        # Retrieve web search context to ground answer generation
        from retrieval.evidence_provide import get_evidence_for_claim
        evidence_list = get_evidence_for_claim(clean_text)
        
        context_str = ""
        if evidence_list:
            context_str = "\n".join([f"- Context snippet: {ev['text']} (Source: {ev['source']})" for ev in evidence_list])

        # Use Gemini model for answer generation if available
        try:
            model = get_gemini_model(api_key)
            if model:
                prompt = (
                    "You are a factual assistant. Provide a highly accurate, detailed, and comprehensive answer to the following question. "
                    "If the question asks for code, provide functional python code blocks wrapped in ```python ... ```.\n"
                    "If the question asks for math, solve it step-by-step.\n\n"
                    f"Question: {clean_text}\n\n"
                )
                if context_str:
                    prompt += (
                        "Use the following retrieved web-grounded search evidence (prioritizing certified sources) to construct your response. "
                        "Make sure your response is fully grounded in the provided facts:\n"
                        f"{context_str}\n\n"
                    )
                
                response = model.generate_content(prompt)
                ans = response.text.strip()
                if ans:
                    return ans, True
        except Exception as e:
            print(f"Gemini answer generation fallback triggered due to error: {str(e)}")

        # Generic fallback: use the best web search evidence as the answer
        if evidence_list:
            # Combine top evidence snippets into a coherent answer
            if len(evidence_list) >= 2:
                combined = "\n".join([f"• {ev['text']} (Source: {ev['source']})" for ev in evidence_list[:3]])
                return f"Based on web search results:\n{combined}", True
            else:
                return f"Search result: {evidence_list[0]['text']} (Source: {evidence_list[0]['source']})", True

        return text, False
        
    return text, False


@app.post("/api/verify")
def verify_answer_endpoint(payload: VerificationRequest):
    """
    Main verification pipeline endpoint.
    Performs ingestion, splits text into prose/code, routes claims to web retrieval verifiers,
    executes code in a secure sandbox, and aggregates results.
    """
    if payload.skip_generation:
        answer_text = payload.answer
        is_generated = False
    else:
        # Auto-generate answer if the input is a question/prompt
        answer_text, is_generated = auto_generate_answer(
            text=payload.answer,
            mode=payload.mode,
            api_key=payload.gemini_api_key
        )

    try:
        # 1. Ingest answer metadata using the actual answer_text (which might be generated)
        ingested = ingest_answer(answer_text, payload.source_model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Chunk text into prose sentences and markdown code blocks
    chunks = chunk_answer(ingested["answer_text"])
    
    # 3. Route chunks dynamically to respective verification handlers
    verified_chunks = []
    
    for chunk in chunks:
        if chunk["type"] == "prose":
            # Verify factual prose claims
            res = verify_fact(
                claim=chunk["content"],
                mode=payload.mode,
                gemini_api_key=payload.gemini_api_key
            )
            verified_chunks.append({
                "type": "prose",
                "content": chunk["content"],
                "verdict": res["verdict"],
                "confidence": res["confidence"],
                "credibility_score": res.get("credibility_score", res["confidence"]),
                "evidence": res["evidence"],
                "explanation": res.get("explanation", "")
            })
            
        elif chunk["type"] == "code":
            # Parse, execute, and verify test assertions in code sandbox
            use_gemini = (payload.mode == "gemini")
            res = verify_code_chunk(
                chunk=chunk,
                use_gemini=use_gemini,
                api_key=payload.gemini_api_key
            )
            verified_chunks.append(res)

    # 4. Aggregate findings into unified confidence assessments
    aggregated_report = aggregate_claim_results(verified_chunks)
    
    # 5. Compile full payload for persistence
    full_report = {
        "id": ingested["id"],
        "timestamp": ingested["timestamp"],
        "source_model": ingested["source_model"],
        "mode_selected": payload.mode,
        "metrics": aggregated_report,
        "chunks": verified_chunks,
        "original_prompt": payload.answer if is_generated else None,
        "generated_answer": answer_text if is_generated else None
    }
    
    # 6. Save report in local database
    save_history(full_report)
    
    return full_report


@app.get("/api/history")
def get_history_endpoint():
    """Retrieves all past logs of verification reports."""
    return load_history()


class CodeVerificationRequest(BaseModel):
    code: str
    language: str = "python"
    source_model: str = "User"
    gemini_api_key: str = None


@app.post("/api/verify-code")
def verify_code_endpoint(payload: CodeVerificationRequest):
    """
    Dedicated code-only verification endpoint.
    Accepts raw code (no markdown wrapping needed) and runs it through
    the full code verification pipeline: static analysis, sandbox execution,
    test generation, and time complexity analysis.
    """
    import uuid
    from datetime import datetime

    code_text = payload.code.strip()
    if not code_text:
        raise HTTPException(status_code=400, detail="No code provided.")

    use_gemini = bool(payload.gemini_api_key)
    chunk = {
        "type": "code",
        "language": payload.language,
        "content": code_text
    }

    res = verify_code_chunk(
        chunk=chunk,
        use_gemini=use_gemini,
        api_key=payload.gemini_api_key
    )

    # Build a full report so the frontend can render it with the same dashboard
    sa = res.get("static_analysis", {})
    tr = res.get("test_results", {})

    code_passed = 1 if res.get("verdict") == "PASS" else 0
    code_failed = 1 if res.get("verdict") == "FAIL" else 0
    code_unsafe = 1 if res.get("verdict") == "UNSAFE" else 0

    score = 90 if code_passed else (30 if code_failed else 10)
    verdict_label = "TRUSTWORTHY" if code_passed else ("UNTRUSTWORTHY" if code_failed else "UNSAFE")

    full_report = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "source_model": payload.source_model,
        "mode_selected": "gemini" if use_gemini else "nli",
        "metrics": {
            "overall_verdict": verdict_label,
            "confidence": score / 100,
            "score_percentage": score,
            "summary": f"Code block verdict: {res.get('verdict', 'UNKNOWN')}. "
                       f"Complexity: {sa.get('complexity', 'N/A')}. "
                       f"Big-O: {sa.get('time_complexity_big_o', 'Unknown')}.",
            "breakdown": f"Code metrics: {code_passed} passed, {code_failed} failed, {code_unsafe} unsafe executions.",
            "metrics": {
                "prose_total": 0,
                "prose_supported": 0,
                "prose_contradicted": 0,
                "prose_neutral": 0,
                "code_total": 1,
                "code_passed": code_passed,
                "code_failed": code_failed,
                "code_unsafe": code_unsafe
            }
        },
        "chunks": [res],
        "original_prompt": None,
        "generated_answer": None
    }

    save_history(full_report)
    return full_report


# Legacy endpoint for Role A Claim Extraction
@app.post("/extract-claims", response_model=ClaimsOutput)
def extract_claims_api(data: AnswerInput):
    """
    Legacy API endpoint matching original Role A requirements.
    Extracts only factual claim strings from AI-generated answer.
    """
    claims = extract_claims(data.answer)
    return {"claims": claims}


# Health Check Endpoint
@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "CodeNeuron API"}


# Serve Frontend Web Dashboard
@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serves the main frontend Single Page Application (SPA)."""
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    # Default visual fallbacks if files don't exist yet
    return HTMLResponse("<h1>CodeNeuron - Loading Frontend Assets...</h1>")


# Mount static assets directory
static_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    print("Launching CodeNeuron full-stack verification server...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

