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

    # 3. Filter out structured fallback boilerplate to avoid verifying non-factual sentences
    boilerplate_patterns = [
        r"### Generated Assessment Response",
        r"You asked: \*\*.*?\*\*",
        r"Based on internal knowledge and search results, here is the detailed breakdown:",
        r"\*\*Web References:\*\*",
        r"No web search context was retrieved for this prompt\.",
        r"\*\*Note:\*\* \*The generative engine \(Gemini\) could not be reached, so this is a structured fallback response\. Ensure your API connectivity is valid\.\*",
        r"Here is a functional boilerplate template for your request:",
        r"\*\s*\(Source:.*?\)\s*\*",
        r"\[.*?\]\s*"
    ]
    for pattern in boilerplate_patterns:
        prose_text = re.sub(pattern, "", prose_text, flags=re.DOTALL | re.IGNORECASE)

    # Clean up empty list bullets and extra whitespace
    prose_text = re.sub(r"^\s*-\s*$", "", prose_text, flags=re.MULTILINE)
    prose_text = prose_text.strip()

    # 4. Split prose into individual sentences (splitting on . ! or ? followed by whitespace)
    # This prevents splitting decimal numbers or short abbreviations
    sentences = re.split(r'(?<=[.!?])\s+', prose_text)
    for sentence in sentences:
        cleaned = sentence.strip()
        # Filter out random punctuation-only lines or too short strings
        cleaned = re.sub(r'\s+', ' ', cleaned) # normalize spaces
        if len(cleaned.split()) >= 5 and not cleaned.startswith("```"):
            # Code heuristic: if sentence has {} it's likely raw code pasted without backticks
            if re.search(r'[{}]', cleaned) or "def " in cleaned or "print(" in cleaned or "return " in cleaned:
                lang = "python"
                if "public static void main" in cleaned or "System.out.print" in cleaned:
                    lang = "java"
                elif "#include" in cleaned or "int main" in cleaned or "printf(" in cleaned:
                    lang = "c"

                chunks.append({
                    "type": "code",
                    "language": lang,
                    "content": cleaned
                })
            else:
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


