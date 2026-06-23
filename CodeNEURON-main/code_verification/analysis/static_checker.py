import ast

def static_check(code: str):
    """
    Performs real static analysis and security auditing on Python code blocks.
    Parses the code using AST to find syntax errors, dangerous nodes, and complexity.
    """
    if not code or not code.strip():
        return {
            "lint_errors": 0,
            "security_issues": 0,
            "complexity": "LOW",
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

    # 2. Parse AST for structural and security auditing
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            "lint_errors": lint_errors + 1,
            "security_issues": 0,
            "complexity": "N/A (Syntax Error)",
            "warnings": [f"Syntax Error on line {e.lineno}: {e.msg}"],
            "details": details + [f"Syntax Error on line {e.lineno}, col {e.offset}: {e.msg}"]
        }

    # Walking the AST nodes
    decision_points = 0
    
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
            # Checking direct call (e.g. eval())
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in ["eval", "exec", "compile", "__import__"]:
                    security_issues += 1
                    warnings.append(f"Security Warning: Direct execution of built-in function '{func_name}()'.")
            
            # Checking attribute call (e.g. os.system() or subprocess.run())
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

    # Cyclomatic complexity grading (McCabe scale approximation)
    complexity_val = decision_points + 1
    if complexity_val <= 3:
        complexity = "LOW"
    elif complexity_val <= 7:
        complexity = "MEDIUM"
    else:
        complexity = "HIGH"

    return {
        "lint_errors": lint_errors,
        "security_issues": security_issues,
        "complexity": f"{complexity} (Score: {complexity_val})",
        "warnings": warnings,
        "details": details
    }

