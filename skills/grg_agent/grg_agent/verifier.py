#!/usr/bin/env python3
"""Code Verifier - External verification tools for generated code"""

import subprocess
import tempfile
import os
import sys
import ast
import typing
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .config import GRGAgentConfig
from .state import Candidate


@dataclass
class VerificationResult:
    """Result of code verification"""
    passed: bool
    execution_success: bool
    type_check_passed: bool
    tests_passed: bool
    errors: List[str]
    output: str
    execution_time: float


class CodeVerifier:
    """
    Verifies generated code using external tools:
    - Execution (Python)
    - Type checking (mypy if available)
    - Test execution
    """
    
    def __init__(self, config: 'GRGAgentConfig'):
        self.config = config
        self.timeout = config.verify_timeout
    
    def verify(self, candidate: 'Candidate', prompt: str, tests: Optional[str] = None) -> VerificationResult:
        """
        Run all verification checks on a candidate.
        
        Returns VerificationResult with details.
        """
        errors = []
        execution_success = False
        type_check_passed = False
        tests_passed = False
        output = ""
        execution_time = 0.0
        
        # Extract clean code from candidate
        code = self._extract_code(candidate.text)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # 1. Syntax check
            try:
                with open(temp_file, 'r') as f:
                    source = f.read()
                ast.parse(source)
            except SyntaxError as e:
                return VerificationResult(
                    passed=False,
                    execution_success=False,
                    type_check_passed=False,
                    tests_passed=False,
                    errors=[f"Syntax error: {e}"],
                    output="",
                    execution_time=0.0
                )
            
            # 2. Execution test
            import time
            start_time = time.time()
            
            try:
                # Run with test cases if provided
                if tests:
                    test_code = f"{candidate.text}\n\n{tests}"
                else:
                    test_code = candidate.text
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_code)
                    test_file = f.name
                
                result = subprocess.run(
                    [sys.executable, test_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                execution_time = time.time() - start_time
                
                if result.returncode == 0:
                    execution_success = True
                    output = result.stdout
                    tests_passed = True
                else:
                    errors.append(f"Execution failed: {result.stderr}")
                    output = result.stderr
                
                os.unlink(test_file)
                
            except subprocess.TimeoutExpired:
                errors.append(f"Execution timeout ({self.timeout}s)")
            except Exception as e:
                errors.append(f"Execution error: {e}")
            
            # 3. Type checking (if mypy available)
            if execution_success:
                type_check_passed, type_errors = self._run_type_check(temp_file)
                errors.extend(type_errors)
                if type_check_passed:
                    type_check_passed = True
            
        finally:
            # Cleanup
            try:
                os.unlink(temp_file)
            except:
                pass
        
        passed = execution_success and (not self.config.verify_execution or tests_passed)
        
        return VerificationResult(
            passed=passed,
            execution_success=execution_success,
            type_check_passed=type_check_passed,
            tests_passed=tests_passed,
            errors=errors,
            output=output,
            execution_time=execution_time
        )
    
    def _run_type_check(self, file_path: str) -> Tuple[bool, List[str]]:
        """Run mypy type checking if available"""
        try:
            result = subprocess.run(
                ["mypy", "--strict", file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return True, []
            else:
                return False, [f"Type check: {result.stdout}"]
        except FileNotFoundError:
            return True, []  # mypy not installed, skip
        except Exception as e:
            return False, [f"Type check error: {e}"]
    
    def _extract_code(self, text: str) -> str:
        """Extract clean Python code from model output, removing markdown and extra text."""
        import re
        
        # Try to extract code from markdown code blocks
        code_blocks = re.findall(r'```(?:python)?\n(.*?)\n```', text, re.DOTALL)
        if code_blocks:
            # Return the largest code block
            return max(code_blocks, key=len).strip()
        
        # If no code blocks, try to extract lines that look like Python code
        lines = text.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            stripped = line.strip()
            # Skip markdown artifacts
            if stripped.startswith('```') or stripped.startswith('# ') or stripped.startswith('## '):
                continue
            # Start collecting after first def/class/import
            if not in_code and (stripped.startswith('def ') or stripped.startswith('class ') or 
                               stripped.startswith('import ') or stripped.startswith('from ')):
                in_code = True
            if in_code:
                code_lines.append(line)
        
        if code_lines:
            return '\n'.join(code_lines).strip()
        
        # Fallback: return original text
        return text.strip()
    
    def extract_tests_from_prompt(self, prompt: str) -> Optional[str]:
        """Extract test cases from prompt if present"""
        # Look for test patterns
        import re
        
        # Look for assert statements or test functions
        lines = prompt.split('\n')
        test_lines = []
        in_test = False
        
        for line in lines:
            if 'assert' in line or 'test_' in line or 'def test' in line:
                in_test = True
            if in_test:
                test_lines.append(line)
                if line.strip() == '' and len(test_lines) > 1:
                    break
        
        if test_lines:
            return '\n'.join(test_lines)
        return None
    
    def generate_tests_for_prompt(self, prompt: str, entry_point: Optional[str] = None) -> str:
        """Generate basic test scaffold for a prompt"""
        # Extract function name
        import re
        match = re.search(r'def\s+(\w+)', prompt)
        fn_name = match.group(1) if match else "solution"
        
        return f'''
# Test cases for {fn_name}
def test_{fn_name}():
    # TODO: Add test cases
    pass

if __name__ == "__main__":
    test_{fn_name}()
    print("All tests passed!")
'''
    
    def verify_batch(self, candidates: List['Candidate'], prompt: str) -> List[VerificationResult]:
        """Verify multiple candidates"""
        return [self.verify(c, prompt) for c in candidates]


def create_verifier(config: 'GRGAgentConfig') -> 'CodeVerifier':
    """Factory function to create verifier"""
    return CodeVerifier(config)