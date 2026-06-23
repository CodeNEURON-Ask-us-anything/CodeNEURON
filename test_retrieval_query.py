from retrieval.evidence_provide import extract_search_query, get_evidence_for_claim

claim = "It lasted somewhere between 38 and 45 minutes, ending after the British navy bombarded the sultan's palace."

print("Query:")
print(extract_search_query(claim))

print("\nResults:")
import pprint
pprint.pprint(get_evidence_for_claim(claim))
