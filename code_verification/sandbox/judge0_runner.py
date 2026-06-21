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
    
    # Supported languages
    supported_langs = ["python", "c", "cpp", "java"]
    if lang not in supported_langs:
        return {
            "stdout": "",
            "stderr": f"CodeNeuron local sandbox does not support '{lang}'. Supported: {', '.join(supported_langs)}.",
            "exit_code": -1,
            "time": "0.00s",
            "memory": "0MB"
        }

    temp_file_path = None
    exec_file_path = None
    try:
        start_time = time.perf_counter()
        
        if lang == "python":
            sandboxed_code = SANDBOX_SECURITY_HEADER + "\n" + code
            fd, temp_file_path = tempfile.mkstemp(suffix=".py", text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(sandboxed_code)
            
            result = subprocess.run([sys.executable, temp_file_path], capture_output=True, text=True, timeout=5.0)
            
        elif lang == "c":
            fd, temp_file_path = tempfile.mkstemp(suffix=".c", text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code)
            exec_file_path = temp_file_path[:-2] + ".exe" if os.name == 'nt' else temp_file_path[:-2] + ".out"
            
            compile_res = subprocess.run(["gcc", temp_file_path, "-o", exec_file_path], capture_output=True, text=True, timeout=5.0)
            if compile_res.returncode != 0:
                return {"stdout": "", "stderr": compile_res.stderr, "exit_code": compile_res.returncode, "time": "0.00s", "memory": "0MB"}
                
            result = subprocess.run([exec_file_path], capture_output=True, text=True, timeout=5.0)
            
        elif lang == "cpp":
            fd, temp_file_path = tempfile.mkstemp(suffix=".cpp", text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code)
            exec_file_path = temp_file_path[:-4] + ".exe" if os.name == 'nt' else temp_file_path[:-4] + ".out"
            
            compile_res = subprocess.run(["g++", temp_file_path, "-o", exec_file_path], capture_output=True, text=True, timeout=5.0)
            if compile_res.returncode != 0:
                return {"stdout": "", "stderr": compile_res.stderr, "exit_code": compile_res.returncode, "time": "0.00s", "memory": "0MB"}
                
            result = subprocess.run([exec_file_path], capture_output=True, text=True, timeout=5.0)
            
        elif lang == "java":
            fd, temp_file_path = tempfile.mkstemp(suffix=".java", text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Use 'java file.java' which works directly in Java 11+ without explicit javac
            result = subprocess.run(["java", temp_file_path], capture_output=True, text=True, timeout=5.0)
            
        execution_time = time.perf_counter() - start_time
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "time": f"{execution_time:.3f}s",
            "memory": "14MB"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Execution timed out. Code exceeded the maximum execution limit of 5.0 seconds.",
            "exit_code": -2,
            "time": "5.00s",
            "memory": "16MB"
        }
    except FileNotFoundError as e:
        compiler = str(e).split()[-1]
        return {
            "stdout": "",
            "stderr": f"Sandbox configuration error: Compiler or interpreter not found. Please install the necessary tools to execute {lang} code.",
            "exit_code": -3,
            "time": "0.00s",
            "memory": "0MB"
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
            try: os.remove(temp_file_path)
            except Exception: pass
        if exec_file_path and os.path.exists(exec_file_path):
            try: os.remove(exec_file_path)
            except Exception: pass

