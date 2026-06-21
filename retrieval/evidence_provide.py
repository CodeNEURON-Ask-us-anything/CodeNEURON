import re
import urllib.parse
import requests
from html.parser import HTMLParser

# List of certified and trusted websites
HIGH_TRUST_DOMAINS = [
    # Government, Academic, and international orgs
    ".gov", ".mil", ".edu", "who.int", "un.org", "nasa.gov",
    # Reference/Encyclopedia
    "wikipedia.org", "britannica.com", "merriam-webster.com", "dictionary.com",
    # Respected Science & Health Databases
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "arxiv.org", "nature.com",
    "science.org", "sciencedirect.com",
    # Reputable news agencies & fact checkers
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com",
    "washingtonpost.com", "wsj.com", "bloomberg.com", "economist.com",
    "snopes.com", "factcheck.org", "politifact.com"
]

MEDIUM_TRUST_DOMAINS = [
    # Official Tech & Programming Documentation
    "docs.python.org", "python.org", "developer.mozilla.org", "w3.org", "w3schools.com",
    "docs.oracle.com", "docs.microsoft.com", "kubernetes.io", "docker.com",
    "github.com", "stackoverflow.com", "pypi.org", "npmjs.com", "geeksforgeeks.org",
    # Q&A and Community (User requested)
    "quora.com", "reddit.com"
]

# Local mock database used as an offline fallback or cache seed
MOCK_EVIDENCE_DB = [
    {
        "text": "Python uses the Timsort algorithm for sorting lists.",
        "source": "https://docs.python.org/3/howto/sorting.html"
    },
    {
        "text": "Canberra is the capital city of Australia.",
        "source": "https://www.australia.gov.au"
    },
    {
        "text": "New Delhi is the capital city of India.",
        "source": "https://en.wikipedia.org/wiki/New_Delhi"
    }
]

from ddgs import DDGS


def get_domain_score(url: str) -> int:
    """
    Returns the trust score of a domain.
    100 for high trust, 50 for medium trust, 10 for unknown.
    """
    if not url:
        return 10
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        
        # Check High Trust
        for domain in HIGH_TRUST_DOMAINS:
            if domain.startswith("."):
                if hostname.endswith(domain) or hostname == domain[1:]:
                    return 100
            else:
                if hostname == domain or hostname.endswith("." + domain):
                    return 100
                    
        # Check Medium Trust
        for domain in MEDIUM_TRUST_DOMAINS:
            if domain.startswith("."):
                if hostname.endswith(domain) or hostname == domain[1:]:
                    return 50
            else:
                if hostname == domain or hostname.endswith("." + domain):
                    return 50
    except Exception:
        pass
    return 10

def calculate_evidence_score(evidence: dict) -> float:
    """
    Calculates a combined trust score based on domain reputation and recency.
    """
    domain_score = get_domain_score(evidence.get("source", ""))
    
    # Recency Score
    year = None
    timestamp = evidence.get("timestamp")
    text = evidence.get("text", "")
    
    if timestamp:
        m = re.search(r'^(\d{4})', timestamp)
        if m:
            year = int(m.group(1))
            
    if not year:
        # Extract 4 digit years from snippet
        years = [int(y) for y in re.findall(r'\b(20\d{2})\b', text)]
        valid_years = [y for y in years if y <= 2026] # Environment simulated up to 2026
        if valid_years:
            year = max(valid_years)
            
    recency_bonus = 0
    if year:
        recency_bonus = max(0, 50 - (2026 - year) * 10)
        
    return domain_score + recency_bonus


def search_duckduckgo(query: str):
    """
    Queries DuckDuckGo using the duckduckgo-search library for robust results.
    """
    if not query or len(query.strip()) < 3:
        return []
        
    try:
        ddgs_results = DDGS().text(query, max_results=15)
        results = []
        import html
        for item in ddgs_results:
            title = html.unescape(item.get('title', ''))
            snippet = html.unescape(item.get('body', ''))
            source = item.get('href', '')
            
            # Format text content
            text_entry = f"[{title}] {snippet.strip()}..." if snippet else f"[{title}]"
            
            results.append({
                "text": text_entry,
                "source": source
            })
        return results
    except Exception as e:
        print(f"DuckDuckGo search error: {str(e)}")
        return []


def get_evidence_for_claim(claim: str):
    """
    Retrieves evidence snippets for a claim from all websites (DuckDuckGo + Wikipedia).
    Prioritizes results from certified websites.
    """
    if not claim or len(claim.strip()) < 5:
        return []

    cleaned_claim = claim.strip()
    
    # 1. Query DuckDuckGo (searches all websites)
    ddg_results = search_duckduckgo(cleaned_claim)
    
    # 2. Query Wikipedia (fallback or supplementary)
    wiki_results = []
    try:
        encoded_query = urllib.parse.quote(cleaned_claim)
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&format=json&utf8=1"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            for item in search_results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                clean_snippet = html.unescape(clean_snippet)
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                timestamp = item.get("timestamp", "")
                
                if clean_snippet.strip():
                    wiki_results.append({
                        "text": f"[{title}] {clean_snippet.strip()}...",
                        "source": page_url,
                        "timestamp": timestamp
                    })
    except Exception:
        pass
        
    # Merge and deduplicate results by URL (source)
    seen_sources = set()
    combined_results = []
    
    for r in ddg_results + wiki_results:
        src = r["source"].lower().rstrip('/')
        if src not in seen_sources:
            seen_sources.add(src)
            combined_results.append(r)
            
    # Calculate scores
    for r in combined_results:
        r["trust_score"] = calculate_evidence_score(r)
        
    # Sort results to prioritize high trust and recent URLs
    combined_results.sort(key=lambda x: x["trust_score"], reverse=True)
    
    # If we found any results, return the top 4
    if combined_results:
        return combined_results[:4]
        
    return []
