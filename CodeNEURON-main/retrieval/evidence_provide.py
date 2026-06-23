import re
import urllib.parse
import requests
from html.parser import HTMLParser

# List of certified and trusted websites
CERTIFIED_DOMAINS = [
    # Government, Academic, and international orgs
    ".gov", ".mil", ".edu", ".org", "who.int", "un.org", "nasa.gov",
    # Reference/Encyclopedia
    "wikipedia.org", "britannica.com", "merriam-webster.com", "dictionary.com",
    # Official Tech & Programming Documentation
    "docs.python.org", "python.org", "developer.mozilla.org", "w3.org", "w3schools.com",
    "docs.oracle.com", "docs.microsoft.com", "kubernetes.io", "docker.com",
    "github.com", "stackoverflow.com", "pypi.org", "npmjs.com",
    # Respected Science & Health Databases
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "arxiv.org", "nature.com",
    "science.org", "sciencedirect.com",
    # Reputable news agencies & fact checkers
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com",
    "washingtonpost.com", "wsj.com", "bloomberg.com", "economist.com",
    "snopes.com", "factcheck.org", "politifact.com",
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

class DDGHTMLParser(HTMLParser):
    """
    A lightweight HTML parser to extract search result URLs and text from DuckDuckGo HTML output.
    Uses target redirection URL pairing to associate titles and snippets reliably.
    """
    def __init__(self):
        super().__init__()
        self.results = []
        self.current_link = None
        self.temp_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            # Look for external target redirection links
            if "uddg=" in href:
                self.current_link = href
                self.temp_text = []

    def handle_endtag(self, tag):
        if tag == "a" and self.current_link:
            link_text = "".join(self.temp_text).strip()
            self.results.append((self.current_link, link_text))
            self.current_link = None

    def handle_data(self, data):
        if self.current_link is not None:
            self.temp_text.append(data)


def is_certified_url(url: str) -> bool:
    """
    Heuristic check to determine if a URL belongs to a certified or trusted domain.
    """
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        
        for domain in CERTIFIED_DOMAINS:
            if domain.startswith("."):
                if hostname.endswith(domain) or hostname == domain[1:]:
                    return True
            else:
                if hostname == domain or hostname.endswith("." + domain):
                    return True
    except Exception:
        pass
    return False


def search_duckduckgo(query: str):
    """
    Queries the live, free DuckDuckGo HTML Search interface.
    Parses and returns a list of results from all websites.
    """
    if not query or len(query.strip()) < 3:
        return []
        
    cleaned_query = query.strip()
    encoded_query = urllib.parse.quote(cleaned_query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    # Use a realistic User-Agent to avoid getting rate-limited or blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            parser = DDGHTMLParser()
            parser.feed(response.text)
            
            parsed_results = {}
            for raw_url, text in parser.results:
                try:
                    parsed_query = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    if "uddg" in parsed_query:
                        real_url = parsed_query["uddg"][0]
                    else:
                        real_url = raw_url
                except Exception:
                    real_url = raw_url
                
                # Normalize protocol relative URLs
                if real_url.startswith("//"):
                    real_url = "https:" + real_url
                
                # Filter out DuckDuckGo internal links
                if "duckduckgo.com" in real_url and "uddg=" not in raw_url:
                    continue
                    
                if real_url not in parsed_results:
                    parsed_results[real_url] = {"title": text, "snippet": "", "source": real_url}
                else:
                    existing = parsed_results[real_url]
                    if not existing["snippet"]:
                        existing["snippet"] = text
                    else:
                        existing["snippet"] += " " + text
            
            results = []
            for item in parsed_results.values():
                title = item["title"]
                snippet = item["snippet"]
                source = item["source"]
                
                # Format text content
                text_entry = f"[{title}] {snippet.strip()}..." if snippet else f"[{title}]"
                
                # Clean HTML tags and entities
                text_entry = re.sub(r'<[^>]+>', '', text_entry)
                text_entry = text_entry.replace("&quot;", "\"").replace("&amp;", "&")
                
                results.append({
                    "text": text_entry,
                    "source": source
                })
            return results
    except Exception as e:
        print(f"DuckDuckGo search error: {str(e)}")
        pass
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
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            for item in search_results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                clean_snippet = re.sub(r'<[^>]+>', '', snippet)
                clean_snippet = clean_snippet.replace("&quot;", "\"").replace("&amp;", "&")
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                
                if clean_snippet.strip():
                    wiki_results.append({
                        "text": f"[{title}] {clean_snippet.strip()}...",
                        "source": page_url
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
            
    # Sort results to prioritize certified URLs
    combined_results.sort(key=lambda x: is_certified_url(x["source"]), reverse=True)
    
    # If we found any results, return the top 4
    if combined_results:
        return combined_results[:4]
        
    # 3. Fallback: Local offline mock database
    results = []
    for ev in MOCK_EVIDENCE_DB:
        claim_words = {w.strip('.,!?;:"()') for w in cleaned_claim.lower().split() if len(w) > 3}
        evidence_words = {w.strip('.,!?;:"()') for w in ev["text"].lower().split() if len(w) > 3}
        overlap = claim_words.intersection(evidence_words)
        if overlap:
            results.append((len(overlap), ev))
            
    results.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in results]
