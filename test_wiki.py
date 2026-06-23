import urllib.parse
import requests

def test_wiki(claim):
    words = claim.lower().split()
    stopwords = {"is", "are", "was", "were", "the", "a", "an", "of", "in", "on", "at", "to", "for", "by", "with", "about"}
    keywords = " ".join([w for w in words if w not in stopwords])
    encoded_query = urllib.parse.quote(keywords)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_query}&format=json&utf8=1"
    response = requests.get(url, timeout=5)
    if response.status_code == 200:
        data = response.json()
        search_results = data.get("query", {}).get("search", [])
        return [item.get("title", "") for item in search_results]
    return []

print(test_wiki("Chief minister of Karnataka is Siddhuramaaya"))
