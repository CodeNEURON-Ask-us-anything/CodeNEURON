import sys
sys.path.append(r"c:\Users\nisha\Downloads\CodeNEURON-main\CodeNEURON-main")
from verification.gemini_verifier import verify_with_gemini

claim1 = "Integration of 1/(1+x2) for limit [0,1] is pi/4"
claim2 = "Chief minister of Karnataka is Siddhuramaaya"

print("Claim 1 Gemini:", verify_with_gemini(claim1))
print("Claim 2 Gemini:", verify_with_gemini(claim2))
