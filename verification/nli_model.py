# Global reference to pipeline, lazy-loaded on demand
_nli_pipeline = None

def run_nli(premise: str, hypothesis: str):
    """
    Runs Natural Language Inference (NLI) on the premise (evidence) and hypothesis (claim).
    Uses 'facebook/bart-large-mnli' model which is lazy-loaded on the first call.
    """
    global _nli_pipeline
    
    if _nli_pipeline is None:
        try:
            from transformers import pipeline
            print("Loading Hugging Face NLI model ('facebook/bart-large-mnli'). This may take a moment...")
            _nli_pipeline = pipeline(
                "text-classification",
                model="facebook/bart-large-mnli"
            )
            print("NLI model loaded successfully.")
        except Exception as e:
            # Fallback or descriptive error raising
            raise RuntimeError(
                f"Failed to initialize Hugging Face NLI pipeline. "
                f"Ensure 'transformers' and 'torch' are fully installed. Error details: {str(e)}"
            )

    # Format input for BART NLI model
    input_text = f"{premise} </s></s> {hypothesis}"
    output = _nli_pipeline(input_text)[0]

    return {
        "label": output["label"],        
        "confidence": round(output["score"], 3)
    }

