def generate_code_verdict(exec_result, test_result, static_result):
    """
    Decides code block execution status based on static issues, runtime exceptions, and assertions.
    """
    if static_result.get("security_issues", 0) > 0:
        return "UNSAFE"
    if exec_result.get("exit_code", 0) != 0 or test_result.get("failed", 0) > 0:
        return "FAIL"
    return "PASS"

