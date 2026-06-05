import re
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

def safe_math_eval(expr_str):
    """
    Evaluates a mathematical expression securely using SymPy.
    Supports complex algebra, calculus, polynomials, etc.
    """
    transformations = (standard_transformations + (implicit_multiplication_application,))
    # parse_expr will raise an error if the expression is invalid
    parsed = parse_expr(expr_str, transformations=transformations)
    return sympy.simplify(parsed)

def evaluate_math_claim(claim: str):
    """
    Tries to evaluate if a claim is a mathematical equality or inequality.
    Returns a dict with verdict, credibility_score, and explanation if it is a math claim, else None.
    """
    clean_claim = claim.strip().lower().rstrip('.')
    
    if '=' not in clean_claim:
        clean_claim = re.sub(r'\b(is|equals)\b', '=', clean_claim)
        
    if '=' not in clean_claim:
        return None
        
    parts = clean_claim.split('=', 1)
    if len(parts) != 2:
        return None
        
    left_expr = parts[0].strip()
    right_expr = parts[1].strip()
    
    # Pre-process exponentiation
    left_expr = left_expr.replace('^', '**')
    right_expr = right_expr.replace('^', '**')
    
    try:
        left_val = safe_math_eval(left_expr)
        right_val = safe_math_eval(right_expr)
        
        # Check equivalence
        diff = sympy.simplify(left_val - right_val)
        is_correct = (diff == 0)
        
        if is_correct:
            return {
                "claim": claim,
                "verdict": "SUPPORTED",
                "confidence": 1.0,
                "credibility_score": 1.0,
                "evidence": {"text": f"Math evaluation: {left_expr} = {left_val}, which matches {right_val}", "source": "SymPy Math Engine"},
                "explanation": "The mathematical claim was successfully verified."
            }
        else:
            return {
                "claim": claim,
                "verdict": "CONTRADICTED",
                "confidence": 1.0,
                "credibility_score": 1.0,
                "evidence": {"text": f"Math evaluation: {left_expr} evaluates to {left_val}, not {right_val}", "source": "SymPy Math Engine"},
                "explanation": "The mathematical claim is incorrect based on algebraic evaluation."
            }
    except Exception:
        # Not a valid simple math equation
        return None

def evaluate_math_expression(expr: str):
    """
    Evaluates a pure mathematical expression (e.g., '2 + 2') and returns the equation and evaluation result.
    If it's not a mathematical expression, returns None.
    """
    clean_expr = expr.strip().lower().rstrip('.')
    clean_expr = clean_expr.replace('^', '**')
    
    try:
        val = safe_math_eval(clean_expr)
        
        # Try to format the value for clean output
        if getattr(val, 'is_Integer', False):
            display_val = int(val)
        elif getattr(val, 'is_Float', False) and val == int(val):
            display_val = int(val)
        else:
            display_val = str(val)
            
        return {
            "expression": expr.strip(),
            "value": display_val,
            "equation": f"{expr.strip()} = {display_val}",
            "credibility_score": 1.0
        }
    except Exception:
        return None
