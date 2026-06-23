import sys
import os

# Add the CodeNEURON directory to sys.path
sys.path.append(r"c:\Users\nisha\Downloads\CodeNEURON-main\CodeNEURON-main")

from retrieval.evidence_provide import get_evidence_for_claim, search_duckduckgo
import urllib.parse
import requests

claim1 = "Integration of 1/(1+x2) for limit [0,1] is pi/4"
claim2 = "Chief minister of Karnataka is Siddhuramaaya"

print("--- DuckDuckGo Search ---")
print("Claim 1:", search_duckduckgo(claim1))
print("Claim 2:", search_duckduckgo(claim2))

print("--- Wikipedia API Search ---")
def wiki(cleaned_claim):
    wiki_results = []
    encoded_query = urllib.parse.quote(cleaned_claim)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&format=json&utf8=1"
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        data = response.json()
        search_results = data.get("query", {}).get("search", [])
        for item in search_results:
            wiki_results.append(item.get("title", ""))
    return wiki_results

print("Wiki Claim 1:", wiki(claim1))
print("Wiki Claim 2:", wiki(claim2))
