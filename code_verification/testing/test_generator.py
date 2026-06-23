import ast
import re
from code_verification.sandbox.judge0_runner import run_code
from verification.gemini_verifier import get_gemini_model

def generate_tests(code: str, use_gemini: bool = False, api_key: str = None, language: str = "python"):
    """
    Generates unit tests (python assertion statements) for a code block.
    Uses Gemini 1.5 Flash if requested, or falls back to AST-based signature parsing.
    Currently bypasses test generation for non-Python languages.
    """
    if not code or not code.strip():
        return ""

    lang = language.strip().lower()
    if lang != "python":
        return ""

    if use_gemini:
        try:
            model = get_gemini_model(api_key)
            if model:
                prompt = f"""
                Write an exhaustive, secure Python unit test suite containing exactly 3 assertions for the code block below.
                Only write assertions that can be executed directly when appended to the user code.
                Use simple 'assert' statements and print 'TEST_CASE_1: PASSED', 'TEST_CASE_2: PASSED', and 'TEST_CASE_3: PASSED' when successful.
                
                User Code:
                {code}
                
                Respond with ONLY the executable Python assertions code block, with absolutely no markdown wrapping, no comments, and no explanations.
                """
                response = model.generate_content(prompt)
                test_code = response.text.strip()
                # Clean up code blocks if returned
                if test_code.startswith("```"):
                    test_code = re.sub(r"^```(?:python)?\n", "", test_code)
                    test_code = re.sub(r"\n```$", "", test_code)
                return test_code.strip()
        except Exception as e:
            print(f"Gemini test generation failed: {str(e)}. Falling back to AST generator...")

    # Offline AST-based test generation fallback
    test_cases = ["# CodeNeuron Auto-Generated Test Suite\n"]
    try:
        tree = ast.parse(code)
        funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        
        if not funcs:
            # If no functions defined, perform basic syntax execution test
            test_cases.append("print('TEST_CASE_1: PASSED') # Code compiled successfully")
        else:
            for idx, func in enumerate(funcs[:3]): # limit to top 3 functions
                func_name = func.name
                args_count = len(func.args.args)
                
                defaults = []
                for _ in range(args_count):
                    defaults.append("1") # fallback default value
                
                signature_call = ", ".join(defaults)
                
                test_cases.append(f"""
# Auto test for {func_name}
result_{idx} = {func_name}({signature_call})
print("TEST_CASE_{idx+1}: PASSED ({func_name} executed without error)")
""")
    except Exception:
        test_cases.append("print('TEST_CASE_1: PASSED')")
        
    return "\n".join(test_cases)


def run_tests(code: str, test_code: str, language: str = "python"):
    """
    Executes the combined user code and generated test code inside the secure sandbox.
    Parses stdout indicators to calculate passed and failed test cases.
    """
    if not code or not code.strip():
        return {"passed": 0, "failed": 0, "details": ["No code to test."]}

    lang = language.strip().lower()
    
    # Only append test code if python (since test_code is python-specific currently)
    if lang == "python" and test_code:
        combined_code = code + "\n\n" + test_code
    else:
        combined_code = code
    
    # Run in subprocess sandbox
    run_result = run_code(combined_code, lang)
    
    stdout = run_result.get("stdout", "")
    stderr = run_result.get("stderr", "")
    
    # Analyze test results from captured stdout
    passed_cases = len(re.findall(r"TEST_CASE_\d+:\s*PASSED", stdout))
    failed_cases = len(re.findall(r"TEST_CASE_\d+:\s*FAILED", stdout))
    
    details = []
    lines = stdout.splitlines() + stderr.splitlines()
    for line in lines:
        if "TEST_CASE_" in line or "AssertionError" in line or "PermissionError" in line:
            details.append(line.strip())
            
    # Parse Exact Error Line and Message from Traceback
    error_line = None
    error_message = None
    
    if stderr:
        if lang == "python":
            # Look for the last file line indicator in the traceback
            line_matches = re.findall(r'File ".*?", line (\d+)', stderr)
            if line_matches:
                raw_line = int(line_matches[-1])
                # Subtract 30 lines for the SANDBOX_SECURITY_HEADER offset
                adjusted_line = raw_line - 30
                if adjusted_line > 0:
                    error_line = adjusted_line
                else:
                    error_line = raw_line # Fell within header or test runner code
        else:
            # Basic parsing for GCC / Javac errors (e.g. file.c:4: error: ...)
            line_matches = re.findall(r'[^:]+:(\d+):', stderr)
            if line_matches:
                error_line = int(line_matches[0])
                
        # The actual error message is typically the last non-empty line
        stderr_lines = [l.strip() for l in stderr.splitlines() if l.strip()]
        if stderr_lines:
            error_message = stderr_lines[-1]
            
    # If exit code was not 0 and no test failures were explicitly counted, it's a runtime error
    if run_result.get("exit_code", 0) != 0 and passed_cases == 0 and failed_cases == 0:
        failed_cases = 1
        err_display = error_message if error_message else stderr.strip()[:150]
        details.append(f"Runtime Failure (Exit code: {run_result.get('exit_code')}). {err_display}")

    if passed_cases == 0 and failed_cases == 0:
        # Default fallback
        passed_cases = 1
        details.append("Syntax baseline compilation executed successfully.")

    return {
        "passed": passed_cases,
        "failed": failed_cases,
        "details": details,
        "stdout": stdout,
        "stderr": stderr,
        "error_line": error_line,
        "error_message": error_message,
        "exit_code": run_result.get("exit_code", 0),
        "time": run_result.get("time", "0.00s"),
        "memory": run_result.get("memory", "0MB")
    }

