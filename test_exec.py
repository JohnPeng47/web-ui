#!/usr/bin/env python3
"""
Test script demonstrating how exec() can modify objects through globals.
"""

from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import traceback


class CodeRunner:
    def __init__(self):
        # Mutable objects that can be modified by exec'd code
        self.shared_list = [1, 2, 3]
        self.shared_dict = {"count": 0, "name": "initial"}
        self.shared_set = {10, 20, 30}
        
        # Set up globals dictionary with references to our objects
        self._globals = {
            "shared_list": self.shared_list,
            "shared_dict": self.shared_dict,
            "shared_set": self.shared_set,
            # Include some built-ins for convenience
            "print": print,
            "len": len,
            "str": str,
        }
    
    def run(self, code: str) -> str:
        """Execute code and return the concatenated stdout+stderr text."""
        stdout_buf = StringIO()
        stderr_buf = StringIO()

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, self._globals, {})
        except Exception:
            traceback.print_exc(file=stderr_buf)

        stdout_text = stdout_buf.getvalue()
        stderr_text = stderr_buf.getvalue()
        return stdout_text + ("\n" + stderr_text if stderr_text else "")
    
    def show_state(self):
        """Display current state of shared objects."""
        print(f"shared_list: {self.shared_list}")
        print(f"shared_dict: {self.shared_dict}")
        print(f"shared_set: {self.shared_set}")
        print("-" * 40)


def main():
    runner = CodeRunner()
    
    print("=== Initial State ===")
    runner.show_state()
    
    # Test 1: Modify list
    print("=== Test 1: Modifying shared_list ===")
    code1 = """
print("Before:", shared_list)
shared_list.append(999)
shared_list[0] = 100
print("After:", shared_list)
"""
    output = runner.run(code1)
    print("Exec output:")
    print(output)
    print("State after exec:")
    runner.show_state()
    
    # Test 2: Modify dictionary
    print("=== Test 2: Modifying shared_dict ===")
    code2 = """
print("Before:", shared_dict)
shared_dict["count"] += 1
shared_dict["new_key"] = "added by exec"
shared_dict["name"] = "modified"
print("After:", shared_dict)
"""
    output = runner.run(code2)
    print("Exec output:")
    print(output)
    print("State after exec:")
    runner.show_state()
    
    # Test 3: Modify set
    print("=== Test 3: Modifying shared_set ===")
    code3 = """
print("Before:", shared_set)
shared_set.add(999)
shared_set.discard(10)
print("After:", shared_set)
"""
    output = runner.run(code3)
    print("Exec output:")
    print(output)
    print("State after exec:")
    runner.show_state()
    
    # Test 4: Multiple operations across calls
    print("=== Test 4: Multiple exec calls maintaining state ===")
    runner.run("shared_dict['call_count'] = 0")
    
    for i in range(3):
        code = f"""
shared_dict['call_count'] += 1
print("Call #" + str(shared_dict['call_count']) + ": Adding item {i + 10}")
shared_list.append({i + 10})
"""
        runner.run(code)
    
    print("Final state after multiple calls:")
    runner.show_state()
    
    # Test 5: Error handling
    print("=== Test 5: Error in exec'd code ===")
    bad_code = """
print("This will work")
shared_list.append("good")
# This will cause an error
x = 1 / 0
print("This won't execute")
"""
    output = runner.run(bad_code)
    print("Exec output (with error):")
    print(output)
    print("State after error (should still have 'good' appended):")
    runner.show_state()


if __name__ == "__main__":
    main()