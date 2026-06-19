from fastapi import FastAPI
from pydantic import BaseModel
from chunking.chunker import extract_claims

app = FastAPI(title="Role A - Claim Extraction API")


# -------- Request Schema --------
class AnswerInput(BaseModel):
    answer: str


# -------- Response Schema --------
class ClaimsOutput(BaseModel):
    claims: list[str]


# -------- API Endpoint --------
@app.post("/extract-claims", response_model=ClaimsOutput)
def extract_claims_api(data: AnswerInput):
    claims = extract_claims(data.answer)
    return {"claims": claims}


# -------- Health Check --------
@app.get("/")
def root():
    return {"status": "Role A API is running"}
