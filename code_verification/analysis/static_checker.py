import ast
from verification.gemini_verifier import get_gemini_model

def static_check(code: str, use_gemini: bool = False, api_key: str = None, language: str = "python"):
    """
    Performs real static analysis and security auditing on Python code blocks.
    Parses the code using AST to find syntax errors, dangerous nodes, and complexity.
    If Gemini is enabled, performs advanced Big-O time complexity analysis and suggests improvements.
    Gracefully skips AST parsing for non-Python languages.
    """
    if not code or not code.strip():
        return {
            "lint_errors": 0,
            "security_issues": 0,
            "complexity": "LOW",
            "time_complexity_big_o": "O(1)",
            "complexity_improvement": "No code provided.",
            "warnings": [],
            "details": []
        }

    lint_errors = 0
    security_issues = 0
    warnings = []
    details = []
    
    # 1. Check for basic formatting/lint issues (e.g. line lengths)
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        if len(line) > 100:
            lint_errors += 1
            details.append(f"Line {idx+1} exceeds 100 characters ({len(line)} chars).")

    lang = language.strip().lower()
    decision_points = 0
    
    # 2. Parse AST for structural and security auditing (Python Only)
    if lang == "python":
        try:
            tree = ast.parse(code)
            
            # Walking the AST nodes
            for node in ast.walk(tree):
                # Cyclomatic complexity indicators
                if isinstance(node, (ast.If, ast.While, ast.For, ast.And, ast.Or, ast.Try, ast.ExceptHandler, ast.FunctionDef, ast.AsyncFunctionDef)):
                    decision_points += 1

                # Check for dangerous imports
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name in ["os", "subprocess", "sys", "socket", "shutil", "pty"]:
                            security_issues += 1
                            warnings.append(f"Security Alert: Restricted import of module '{name.name}'.")
                elif isinstance(node, ast.ImportFrom):
                    if node.module in ["os", "subprocess", "sys", "socket", "shutil", "pty"]:
                        security_issues += 1
                        warnings.append(f"Security Alert: Restricted import from module '{node.module}'.")

                # Check for dangerous function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        if func_name in ["eval", "exec", "compile", "__import__"]:
                            security_issues += 1
                            warnings.append(f"Security Warning: Direct execution of built-in function '{func_name}()'.")
                    elif isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            module_name = node.func.value.id
                            attr_name = node.func.attr
                            if module_name == "os" and attr_name in ["system", "popen", "spawn", "exec"]:
                                security_issues += 1
                                warnings.append(f"Security Alert: Call to restricted OS command execution '{module_name}.{attr_name}()'.")
                            elif module_name == "subprocess" and attr_name in ["run", "Popen", "call", "check_output"]:
                                security_issues += 1
                                warnings.append(f"Security Alert: Call to restricted shell execution '{module_name}.{attr_name}()'.")
        except SyntaxError as e:
            return {
                "lint_errors": lint_errors + 1,
                "security_issues": 0,
                "complexity": "N/A (Syntax Error)",
                "time_complexity_big_o": "Unknown",
                "complexity_improvement": "Fix syntax errors before analysis.",
                "warnings": [f"Syntax Error on line {e.lineno}: {e.msg}"],
                "details": details + [f"Syntax Error on line {e.lineno}, col {e.offset}: {e.msg}"]
            }

    # Cyclomatic complexity grading (McCabe scale approximation)
    complexity_val = decision_points + 1
    if complexity_val <= 3:
        complexity = "LOW"
    elif complexity_val <= 7:
        complexity = "MEDIUM"
    else:
        complexity = "HIGH"
        
    time_complexity_big_o = "Unknown"
    complexity_improvement = "LLM required for Big-O analysis."
    
    if use_gemini:
        try:
            model = get_gemini_model(api_key)
            if model:
                prompt = f"""
                Analyze the following Python code and determine its Big-O Time Complexity.
                Then, briefly suggest how the time complexity can be improved.
                Format your response strictly as two lines:
                O(...)
                Improvement: ...
                
                Code:
                {code}
                """
                resp = model.generate_content(prompt)
                lines = resp.text.strip().split('\n')
                if lines:
                    time_complexity_big_o = lines[0].strip()
                    if len(lines) > 1:
                        complexity_improvement = " ".join([l.strip() for l in lines[1:] if l.strip()]).replace("Improvement:", "").strip()
        except Exception as e:
            print(f"Gemini complexity analysis failed: {str(e)}")

    return {
        "lint_errors": lint_errors,
        "security_issues": security_issues,
        "complexity": f"{complexity} (Score: {complexity_val})",
        "time_complexity_big_o": time_complexity_big_o,
        "complexity_improvement": complexity_improvement,
        "warnings": warnings,
        "details": details
    }

