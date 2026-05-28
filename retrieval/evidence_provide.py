import re
import urllib.parse
import requests

# Local mock database used as an offline fallback or cache seed
MOCK_EVIDENCE_DB = [
    {
        "text": "Python uses the Timsort algorithm for sorting lists.",
        "source": "https://docs.python.org/3/howto/sorting.html"
    },
    {
        "text": "Canberra is the capital city of Australia.",
        "source": "https://www.australia.gov.au"
    }
]

def get_evidence_for_claim(claim: str):
    """
    Retrieves evidence snippets for a claim.
    Queries the live, free Wikipedia Search API.
    Falls back to a local mock database on network issues or no-results.
    """
    if not claim or len(claim.strip()) < 5:
        return []

    cleaned_claim = claim.strip()
    
    # Attempt Wikipedia API search retrieval
    try:
        # Wikipedia search API URL
        encoded_query = urllib.parse.quote(cleaned_claim)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&format=json&utf8=1"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            
            results = []
            for item in search_results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                
                # Clean HTML tags (like <b>...</b>) from Wikipedia snippet
                clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                clean_snippet = clean_snippet.replace("&quot;", "\"").replace("&amp;", "&")
                
                # Construct official Wikipedia page URL
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                
                if clean_snippet.strip():
                    results.append({
                        "text": f"[{title}] {clean_snippet.strip()}...",
                        "source": page_url
                    })
            
            if results:
                return results[:3]  # return top 3 relevant results
    except Exception as e:
        # Log error or print in debug mode
        pass

    # Network failure or empty search fallback: Search our local mock database
    results = []
    for ev in MOCK_EVIDENCE_DB:
        # Simple keyword overlap to see if mock data is relevant
        claim_words = set(cleaned_claim.lower().split())
        evidence_words = set(ev["text"].lower().split())
        if claim_words.intersection(evidence_words):
            results.append(ev)
            
    return results

