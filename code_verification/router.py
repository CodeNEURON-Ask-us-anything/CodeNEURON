from code_verification.analysis.static_checker import static_check
from code_verification.testing.test_generator import generate_tests, run_tests
from code_verification.verdict import generate_code_verdict

def is_code_chunk(chunk: dict) -> bool:
    return chunk.get("type") == "code"


def route_code(chunk: dict):
    return {
        "language": chunk.get("language", "python"),
        "code": chunk.get("content")
    }


def verify_code_chunk(chunk: dict, use_gemini: bool = False, api_key: str = None):
    """
    Core orchestrator for checking, compiling, and executing code chunks safely.
    Integrates static checks, AST lints, test generation, sandboxed execution, and verdict determination.
    """
    code_text = chunk.get("content", "")
    language = chunk.get("language", "python")
    
    # 1. Perform static analysis & security auditing (and optional Big-O analysis via Gemini)
    static_results = static_check(code_text, use_gemini, api_key, language=language)
    
    # 2. Compile tests (either Gemini LLM generated or static AST fallback)
    generated_test_code = generate_tests(code_text, use_gemini, api_key, language=language)
    
    # 3. Securely execute target code combined with test code inside sandbox
    test_run_results = run_tests(code_text, generated_test_code, language=language)
    
    # 4. Generate unified code assessment status (PASS, FAIL, UNSAFE)
    # Replicate fake runner results payload mapping to execute verdict
    exec_result_simulation = {
        "stdout": test_run_results.get("stdout", ""),
        "stderr": test_run_results.get("stderr", ""),
        "exit_code": test_run_results.get("exit_code", 0)
    }
    
    verdict = generate_code_verdict(
        exec_result=exec_result_simulation,
        test_result={"failed": test_run_results.get("failed", 0)},
        static_result={"security_issues": static_results.get("security_issues", 0)}
    )
    
    return {
        "type": "code",
        "language": language,
        "code": code_text,
        "verdict": verdict,
        "static_analysis": static_results,
        "test_results": test_run_results,
        "test_source": generated_test_code
    }
