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

def safe_integrate(expr_str):
    """
    Parses and evaluates an integration expression.
    """
    # handle definite integrals: "integrate x^2 from 0 to 1" or "integral of x^2 from 0 to 1"
    # handle indefinite integrals: "integrate x^2" or "integral of x^2"
    expr_str = expr_str.lower().strip()
    expr_str = re.sub(r'^(integrate|integral of|integral)\s+', '', expr_str)
    
    # check for bounds
    match = re.search(r'(.*?)\s+from\s+(.*?)\s+to\s+(.*)', expr_str)
    
    x = sympy.Symbol('x')
    transformations = (standard_transformations + (implicit_multiplication_application,))
    
    if match:
        func_str, lower_str, upper_str = match.groups()
        func_expr = parse_expr(func_str, transformations=transformations)
        lower_bound = parse_expr(lower_str, transformations=transformations)
        upper_bound = parse_expr(upper_str, transformations=transformations)
        result = sympy.integrate(func_expr, (x, lower_bound, upper_bound))
        return func_str, result, f"definite integral from {lower_bound} to {upper_bound}"
    else:
        func_expr = parse_expr(expr_str, transformations=transformations)
        result = sympy.integrate(func_expr, x)
        return expr_str, result, "indefinite integral"

def evaluate_math_claim(claim: str):
    """
    Tries to evaluate if a claim is a mathematical equality or inequality.
    Returns a dict with verdict, credibility_score, and explanation if it is a math claim, else None.
    """
    clean_claim = claim.strip().lower().rstrip('.')
    
    # Heuristic to prevent English sentences from being parsed as algebraic equations:
    # A valid math claim should contain at least one number, or explicit math operators/functions.
    has_math = bool(re.search(r'\d', clean_claim)) or bool(re.search(r'[\+\-\*/\^]|integr|sqrt|sin|cos|tan', clean_claim))
    if not has_math:
        return None
    
    # Check if it's an integration claim like "the integral of x^2 is x^3/3"
    if 'integr' in clean_claim and '=' not in clean_claim:
        clean_claim = re.sub(r'\b(is|equals)\b', '=', clean_claim)
        
    if 'integr' in clean_claim and '=' in clean_claim:
        parts = clean_claim.split('=', 1)
        if len(parts) == 2:
            left_expr = parts[0].strip().replace('^', '**')
            right_expr = parts[1].strip().replace('^', '**')
            try:
                if 'integr' in left_expr:
                    func_str, computed_val, int_type = safe_integrate(left_expr)
                    right_val = safe_math_eval(right_expr)
                    diff = sympy.simplify(computed_val - right_val)
                    is_correct = (diff == 0)
                    
                    if is_correct:
                        return {
                            "claim": claim,
                            "verdict": "SUPPORTED",
                            "confidence": 1.0,
                            "credibility_score": 1.0,
                            "evidence": {"text": f"Math evaluation: The {int_type} of {func_str} is {computed_val}, which matches {right_val}", "source": "SymPy Math Engine"},
                            "explanation": "The mathematical integration claim was successfully verified."
                        }
                    else:
                        return {
                            "claim": claim,
                            "verdict": "CONTRADICTED",
                            "confidence": 1.0,
                            "credibility_score": 1.0,
                            "evidence": {"text": f"Math evaluation: The {int_type} of {func_str} is {computed_val}, not {right_val}", "source": "SymPy Math Engine"},
                            "explanation": "The mathematical integration claim is incorrect based on calculus evaluation."
                        }
            except Exception:
                pass
    
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
    Evaluates a pure mathematical expression (e.g., '2 + 2' or 'integrate x^2') and returns the equation and evaluation result.
    If it's not a mathematical expression, returns None.
    """
    clean_expr = expr.strip().lower().rstrip('.')
    clean_expr = clean_expr.replace('^', '**')
    
    if clean_expr.startswith('integr'):
        try:
            func_str, result_val, int_type = safe_integrate(clean_expr)
            return {
                "expression": expr.strip(),
                "value": str(result_val),
                "equation": f"Integral of {func_str} = {result_val}",
                "credibility_score": 1.0
            }
        except Exception:
            pass
    
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
