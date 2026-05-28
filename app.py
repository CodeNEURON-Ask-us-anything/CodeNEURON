import os
import json
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

app = FastAPI(title="CodeNeuron - AI Answer Verification & Validation Platform")

# Workspace database paths for history logging
HISTORY_DB_PATH = "verification_history.json"

# Base Request Schema
class VerificationRequest(BaseModel):
    answer: str
    source_model: str = "Unknown"
    mode: str = "nli"  # "nli" or "gemini"
    gemini_api_key: str = None

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


@app.post("/api/verify")
def verify_answer_endpoint(payload: VerificationRequest):
    """
    Main verification pipeline endpoint.
    Performs ingestion, splits text into prose/code, routes claims to web retrieval verifiers,
    executes code in a secure sandbox, and aggregates results.
    """
    try:
        # 1. Ingest answer metadata
        ingested = ingest_answer(payload.answer, payload.source_model)
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
        "chunks": verified_chunks
    }
    
    # 6. Save report in local database
    save_history(full_report)
    
    return full_report


@app.get("/api/history")
def get_history_endpoint():
    """Retrieves all past logs of verification reports."""
    return load_history()


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

