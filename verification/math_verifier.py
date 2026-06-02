import ast
import operator
import re
import math

def safe_math_eval(expr):
    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    
    math_env = {
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
        'sqrt': math.sqrt, 'log': math.log, 'log10': math.log10,
        'exp': math.exp, 'pi': math.pi, 'e': math.e,
        'abs': abs, 'round': round
    }

    def eval_node(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            return ops[type(node.op)](eval_node(node.left), eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](eval_node(node.operand))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in math_env:
                args = [eval_node(arg) for arg in node.args]
                return math_env[node.func.id](*args)
            raise TypeError(f"Unsupported function: {node.func.id if isinstance(node.func, ast.Name) else 'Unknown'}")
        elif isinstance(node, ast.Name):
            if node.id in math_env:
                return math_env[node.id]
            raise TypeError(f"Unsupported variable: {node.id}")
        else:
            raise TypeError("Unsupported math operation")
            
    return eval_node(ast.parse(expr, mode='eval').body)

def evaluate_math_claim(claim: str):
    """
    Tries to evaluate if a claim is a mathematical equality or inequality.
    Returns a dict with verdict and explanation if it is a math claim, else None.
    """
    # Normalize the claim
    clean_claim = claim.strip().lower().rstrip('.')
    
    # Simple regex to check if it looks like a math equation (numbers and operators, and an equals sign)
    # E.g. "2 + 2 = 4" or "10 / 2 = 5"
    if '=' not in clean_claim:
        # Sometimes words like "is" or "equals" are used
        clean_claim = re.sub(r'\b(is|equals)\b', '=', clean_claim)
        
    if '=' not in clean_claim:
        return None
        
    parts = clean_claim.split('=', 1)
    if len(parts) != 2:
        return None
        
    left_expr = parts[0].strip()
    right_expr = parts[1].strip()
    
    # Remove all spaces and common English math words if we just want numbers
    # But ast.parse handles spaces fine. Let's make sure it only has valid characters
    valid_chars = set("0123456789.+-*/^() abcdefghijklmnopqrstuvwxyz")
    if not all(c in valid_chars for c in left_expr) or not all(c in valid_chars for c in right_expr):
        return None
        
    # Python uses ** for exponentiation
    left_expr = left_expr.replace('^', '**')
    right_expr = right_expr.replace('^', '**')
    
    try:
        left_val = safe_math_eval(left_expr)
        right_val = safe_math_eval(right_expr)
        
        # Avoid float precision issues
        is_correct = abs(left_val - right_val) < 1e-9
        
        if is_correct:
            return {
                "claim": claim,
                "verdict": "SUPPORTED",
                "confidence": 1.0,
                "evidence": {"text": f"Math evaluation: {left_expr} = {left_val}, which matches {right_val}", "source": "Internal Math Engine"},
                "explanation": "The mathematical claim was successfully verified."
            }
        else:
            return {
                "claim": claim,
                "verdict": "CONTRADICTED",
                "confidence": 1.0,
                "evidence": {"text": f"Math evaluation: {left_expr} evaluates to {left_val}, not {right_val}", "source": "Internal Math Engine"},
                "explanation": "The mathematical claim is incorrect based on arithmetic evaluation."
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
    
    # Python uses ** for exponentiation
    clean_expr = clean_expr.replace('^', '**')
    
    valid_chars = set("0123456789.+-*/^() abcdefghijklmnopqrstuvwxyz")
    if not clean_expr or not all(c in valid_chars for c in clean_expr):
        return None
        
    try:
        val = safe_math_eval(clean_expr)
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        return {
            "expression": expr.strip(),
            "value": val,
            "equation": f"{expr.strip()} = {val}"
        }
    except Exception:
        return None
