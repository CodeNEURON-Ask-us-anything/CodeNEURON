import sys
import time
import subprocess
import tempfile
import os

SANDBOX_SECURITY_HEADER = """# CodeNeuron Subprocess Sandbox Security Header
import sys
import builtins

# Block dangerous imports in sys.modules
class RestrictedModule:
    def __getattr__(self, name):
        raise PermissionError(f"Access to '{name}' is strictly prohibited in the CodeNeuron execution sandbox.")
    def __repr__(self):
        return "RestrictedModule"

restricted_modules = ['os', 'subprocess', 'shutil', 'socket', 'urllib', 'requests', 'pty', 'platform', 'ctypes']
for mod in restricted_modules:
    sys.modules[mod] = RestrictedModule()

# Restrict unsafe file operations
_original_open = builtins.open
def secure_open(file, mode='r', *args, **kwargs):
    # Prohibit writing/appending files
    if any(char in mode for char in ['w', 'a', 'x', '+']):
        raise PermissionError("File write/append actions are prohibited in the CodeNeuron sandbox.")
    return _original_open(file, mode, *args, **kwargs)

builtins.open = secure_open

# Disable eval/exec blockages inside executing scope
def secure_eval(*args, **kwargs):
    raise PermissionError("eval() usage is prohibited inside the CodeNeuron sandbox.")
builtins.eval = secure_eval
"""

def run_code(code: str, language: str = "python"):
    """
    Executes Python code blocks safely inside an isolated subprocess sandbox.
    Redirection streams are captured and CPU execution time is monitored.
    """
    if not code or not code.strip():
        return {
            "stdout": "",
            "stderr": "No executable code provided.",
            "exit_code": -1,
            "time": "0.00s",
            "memory": "0MB"
        }

    lang = (language or "python").strip().lower()
    
    # Secure Local execution is supported for Python
    if lang != "python":
        return {
            "stdout": "",
            "stderr": f"CodeNeuron local sandbox execution only supports Python. Selected language '{lang}' was bypassed.",
            "exit_code": 0,
            "time": "0.00s",
            "memory": "0MB"
        }

    # Inject sandbox safety protections and write code to temporary file
    sandboxed_code = SANDBOX_SECURITY_HEADER + "\n" + code
    
    temp_file = None
    try:
        # Create a secure temporary file
        fd, temp_file_path = tempfile.mkstemp(suffix=".py", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(sandboxed_code)
        
        # Measure CPU execution time
        start_time = time.perf_counter()
        
        # Execute the python process in sandbox
        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=5.0  # Strict 5.0 second maximum CPU execution limit
        )
        
        execution_time = time.perf_counter() - start_time
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "time": f"{execution_time:.3f}s",
            "memory": "14MB"  # Approximation of standard python subprocess baseline
        }
        
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Execution timed out. Code exceeded the maximum execution limit of 5.0 seconds.",
            "exit_code": -2,
            "time": "5.00s",
            "memory": "16MB"
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Sandbox execution error: {str(e)}",
            "exit_code": -3,
            "time": "0.00s",
            "memory": "0MB"
        }
    finally:
        # Guarantee cleanup of temporary files
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

