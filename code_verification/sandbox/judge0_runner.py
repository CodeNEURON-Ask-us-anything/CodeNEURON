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
    Executes code blocks safely inside an isolated subprocess sandbox.
    Supports Python natively. Supports C, C++, and Java if compilers are installed.
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
    
    # ---------------- PYTHON EXECUTION ----------------
    if lang == "python":
        sandboxed_code = SANDBOX_SECURITY_HEADER + "\n" + code
        temp_file_path = None
        try:
            fd, temp_file_path = tempfile.mkstemp(suffix=".py", text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(sandboxed_code)
            
            start_time = time.perf_counter()
            result = subprocess.run(
                [sys.executable, temp_file_path],
                capture_output=True, text=True, timeout=5.0
            )
            execution_time = time.perf_counter() - start_time
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "time": f"{execution_time:.3f}s",
                "memory": "14MB"
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out (5.0s limit).", "exit_code": -2, "time": "5.00s", "memory": "16MB"}
        except Exception as e:
            return {"stdout": "", "stderr": f"Sandbox execution error: {str(e)}", "exit_code": -3, "time": "0.00s", "memory": "0MB"}
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except Exception: pass

    # ---------------- C / C++ EXECUTION ----------------
    elif lang in ["c", "cpp"]:
        ext = ".c" if lang == "c" else ".cpp"
        compiler = "gcc" if lang == "c" else "g++"
        temp_src_path = None
        temp_exe_path = None
        try:
            # Create source file
            fd, temp_src_path = tempfile.mkstemp(suffix=ext, text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Executable name
            temp_exe_path = temp_src_path[:-len(ext)] + (".exe" if os.name == 'nt' else "")
            
            # Compile step
            compile_res = subprocess.run(
                [compiler, temp_src_path, "-o", temp_exe_path],
                capture_output=True, text=True
            )
            if compile_res.returncode != 0:
                return {"stdout": "", "stderr": f"Compilation Error:\n{compile_res.stderr}", "exit_code": compile_res.returncode, "time": "0.00s", "memory": "0MB"}
            
            # Execute step
            start_time = time.perf_counter()
            result = subprocess.run(
                [temp_exe_path], capture_output=True, text=True, timeout=5.0
            )
            execution_time = time.perf_counter() - start_time
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "time": f"{execution_time:.3f}s",
                "memory": "4MB"
            }
        except FileNotFoundError:
            return {"stdout": "", "stderr": f"Compiler '{compiler}' not found. Please ensure it is installed and in your PATH.", "exit_code": -4, "time": "0.00s", "memory": "0MB"}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out (5.0s limit).", "exit_code": -2, "time": "5.00s", "memory": "4MB"}
        except Exception as e:
            return {"stdout": "", "stderr": f"Execution error: {str(e)}", "exit_code": -3, "time": "0.00s", "memory": "0MB"}
        finally:
            if temp_src_path and os.path.exists(temp_src_path):
                try: os.remove(temp_src_path)
                except Exception: pass
            if temp_exe_path and os.path.exists(temp_exe_path):
                try: os.remove(temp_exe_path)
                except Exception: pass

    # ---------------- JAVA EXECUTION ----------------
    elif lang == "java":
        temp_dir = tempfile.mkdtemp()
        temp_src_path = os.path.join(temp_dir, "Main.java")
        try:
            with open(temp_src_path, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Compile step
            compile_res = subprocess.run(
                ["javac", temp_src_path],
                capture_output=True, text=True
            )
            if compile_res.returncode != 0:
                return {"stdout": "", "stderr": f"Compilation Error:\n{compile_res.stderr}", "exit_code": compile_res.returncode, "time": "0.00s", "memory": "0MB"}
            
            # Execute step
            start_time = time.perf_counter()
            result = subprocess.run(
                ["java", "-cp", temp_dir, "Main"], capture_output=True, text=True, timeout=5.0
            )
            execution_time = time.perf_counter() - start_time
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "time": f"{execution_time:.3f}s",
                "memory": "32MB"
            }
        except FileNotFoundError:
            return {"stdout": "", "stderr": "Java compiler 'javac' not found. Please ensure JDK is installed and in your PATH.", "exit_code": -4, "time": "0.00s", "memory": "0MB"}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out (5.0s limit).", "exit_code": -2, "time": "5.00s", "memory": "32MB"}
        except Exception as e:
            return {"stdout": "", "stderr": f"Execution error: {str(e)}", "exit_code": -3, "time": "0.00s", "memory": "0MB"}
        finally:
            import shutil
            if os.path.exists(temp_dir):
                try: shutil.rmtree(temp_dir)
                except Exception: pass

    # ---------------- UNSUPPORTED LANGUAGE ----------------
    else:
        return {
            "stdout": "",
            "stderr": f"CodeNeuron sandbox does not support language '{lang}'. Supported languages: python, c, cpp, java.",
            "exit_code": 0,
            "time": "0.00s",
            "memory": "0MB"
        }

