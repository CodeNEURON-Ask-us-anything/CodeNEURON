import sys
sys.path.append(r"c:\Users\nisha\Downloads\CodeNEURON-main\CodeNEURON-main")
from verification.claim_verifier import direct_matching_fallback

claim1 = "Integration of 1/(1+x2) for limit [0,1] is pi/4"
ev1 = "The mathematical integration of 1/(1+x2) for limit [0,1] is exactly pi/4. This is derived from the arctan rule."

claim2 = "Chief minister of Karnataka is Siddhuramaaya"
ev2 = "The Chief Minister of Karnataka is Siddaramaiah (also spelled Siddhuramaaya). He assumed office in 2023."

print("Math fallback:", direct_matching_fallback(claim1, ev1))
print("CM fallback:", direct_matching_fallback(claim2, ev2))
