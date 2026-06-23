import uuid
from datetime import datetime

def ingest_answer(answer_text: str, source_model: str = "Unknown"):
    """ Takes a raw AI answer and metadata.
    Validates input and returns a structured dictionary with a unique ID.
    """
    if not answer_text or not answer_text.strip():
        raise ValueError("Answer text cannot be empty or blank.")

    cleaned_text = answer_text.strip()
    return {
        "id": str(uuid.uuid4()),
        "source_model": source_model or "Unknown",
        "timestamp": datetime.now().isoformat(),
        "answer_text": cleaned_text,
        "length": len(cleaned_text),
        "word_count": len(cleaned_text.split())
    }