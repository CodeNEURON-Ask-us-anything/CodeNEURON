import re

def chunk_answer(answer_text: str):
    """
    Splits the AI answer into prose chunks (sentences) and code blocks.
    Identifies language tags in markdown code blocks.
    """
    chunks = []

    # 1. Parse code blocks with optional language headers: ```python\ncode\n```
    code_pattern = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
    code_matches = code_pattern.findall(answer_text)
    for lang, code in code_matches:
        chunks.append({
            "type": "code",
            "language": lang.strip().lower() or "python",
            "content": code.strip()
        })

    # 2. Remove code blocks to isolate prose text
    prose_text = re.sub(r"```.*?```", "", answer_text, flags=re.DOTALL)

    # 3. Split prose into individual sentences (splitting on . ! or ? followed by whitespace)
    # This prevents splitting decimal numbers or short abbreviations
    sentences = re.split(r'(?<=[.!?])\s+', prose_text)
    for sentence in sentences:
        cleaned = sentence.strip()
        # Filter out random punctuation-only lines or too short strings
        cleaned = re.sub(r'\s+', ' ', cleaned) # normalize spaces
        if len(cleaned) >= 3 and not cleaned.startswith("```"):
            chunks.append({
                "type": "prose",
                "content": cleaned
            })

    return chunks


def extract_claims(answer_text: str):
    """
    Role A main function used by API and Role B.
    Returns only prose claims (no code blocks).
    """
    chunks = chunk_answer(answer_text)
    return [
        c["content"]
        for c in chunks
        if c["type"] == "prose"
    ]


