#!/usr/bin/env python3
"""
Code Review Agent - Diff Analysis

Reviews git diffs and provides structured findings (block/warn/info).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


class DiffAnalyzer:
    """Analyzes git diffs for issues."""

    def __init__(self):
        self.findings = []

    def add_finding(self, file: str, line: int, severity: str, category: str, rule: str, message: str, suggestion: str = ""):
        """Add a finding to the results."""
        self.findings.append({
            "file": file,
            "line": line,
            "severity": severity,
            "category": category,
            "rule": rule,
            "message": message,
            "suggestion": suggestion
        })

    def analyze_diff(self, diff_text: str) -> List[Dict[str, Any]]:
        """Analyze a git diff and return findings."""
        self.findings = []
        
        # Parse diff
        current_file = None
        current_line = 0
        
        for line in diff_text.split('\n'):
            # File header: +++ b/src/file.py
            if line.startswith('+++ b/'):
                current_file = line[6:]
                current_line = 0
            # Line number header: @@ -10,5 +10,7 @@
            elif line.startswith('@@'):
                match = re.search(r'\+(\d+)', line)
                if match:
                    current_line = int(match.group(1))
            # Added line: +    code
            elif line.startswith('+') and not line.startswith('+++'):
                current_line += 1
                added_line = line[1:]
                if current_file:
                    self._check_line(current_file, current_line, added_line)
            # Context/removed line
            elif line.startswith(' ') or line.startswith('-'):
                if not line.startswith('---'):
                    current_line += 1
        
        return self.findings

    def _check_line(self, file: str, line_num: int, line: str):
        """Check a single line for issues."""
        if not file:
            return

        # Security: Hardcoded secrets
        secret_patterns = [
            (r'(api[_-]?key|secret[_-]?key|password|token)\s*[=:]\s*["\'][^"\']+["\']', 'hardcoded-secret', 'security'),
            (r'(aws[_-]?access[_-]?key|aws[_-]?secret)\s*[=:]\s*["\'][^"\']+["\']', 'aws-credentials', 'security'),
            (r'("|\')sk-[a-zA-Z0-9]{20,}', 'openai-key', 'security'),
        ]
        
        for pattern, rule, category in secret_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                self.add_finding(file, line_num, 'block', category, rule, 
                    f"Potential hardcoded secret detected", 
                    "Use environment variables or secret management")

        # Security: SQL injection risk
        if re.search(r'(execute|query|raw)\s*\(.*.*%.*\)', line):
            self.add_finding(file, line_num, 'warn', 'security', 'sql-injection-risk',
                "Possible SQL injection via string formatting",
                "Use parameterized queries")

        # Pattern: TODO/FIXME without issue reference
        if re.search(r'(TODO|FIXME|XXX)(?!\s*[#\(]\d+)', line):
            self.add_finding(file, line_num, 'info', 'maintainability', 'todo-without-ref',
                "TODO/FIXME without issue reference",
                "Add issue number: TODO(#123): description")

        # Pattern: Print statements in production code
        if re.search(r'\bprint\s*\(', line) and 'test' not in file.lower():
            self.add_finding(file, line_num, 'warn', 'style', 'print-statement',
                "Print statement in production code",
                "Use logging module instead")

        # Pattern: Bare except
        if re.search(r'except\s*:', line):
            self.add_finding(file, line_num, 'warn', 'correctness', 'bare-except',
                "Bare except clause catches all exceptions",
                "Specify exception type: except ValueError:")

        # Pattern: Mutable default argument
        if re.search(r'def\s+\w+\s*\([^)]*=\s*\[', line) or re.search(r'def\s+\w+\s*\([^)]*=\s*\{', line):
            self.add_finding(file, line_num, 'warn', 'correctness', 'mutable-default',
                "Mutable default argument (list/dict)",
                "Use None as default and create inside function")

        # Naming: Function/class naming (basic)
        if re.search(r'def\s+[A-Z][a-zA-Z]*\s*\(', line) and not re.search(r'def\s+__[a-zA-Z]+__', line):
            self.add_finding(file, line_num, 'info', 'naming', 'function-naming',
                "Function name should be snake_case",
                "Rename to snake_case per PEP 8")

        # Import: Star import
        if re.search(r'from\s+\S+\s+import\s+\*', line):
            self.add_finding(file, line_num, 'warn', 'imports', 'star-import',
                "Star import makes dependencies unclear",
                "Import specific names: from module import name1, name2")


def main():
    parser = argparse.ArgumentParser(description="Review git diff for issues")
    parser.add_argument('--diff', required=True, help="Path to diff file or '-' for stdin")
    parser.add_argument('--format', choices=['json', 'text', 'github'], default='json')
    parser.add_argument('--severity', default='block,warn,info', help="Comma-separated severity levels to include")
    parser.add_argument('--output', help="Output file (default: stdout)")
    args = parser.parse_args()

    # Read diff
    if args.diff == '-':
        diff_text = sys.stdin.read()
    else:
        diff_path = Path(args.diff)
        if not diff_path.exists():
            print(f"Error: Diff file not found: {args.diff}", file=sys.stderr)
            sys.exit(1)
        diff_text = diff_path.read_text()

    # Analyze
    analyzer = DiffAnalyzer()
    findings = analyzer.analyze_diff(diff_text)

    # Filter by severity
    allowed_severities = set(args.severity.split(','))
    findings = [f for f in findings if f['severity'] in allowed_severities]

    # Summary
    summary = {
        'block': sum(1 for f in findings if f['severity'] == 'block'),
        'warn': sum(1 for f in findings if f['severity'] == 'warn'),
        'info': sum(1 for f in findings if f['severity'] == 'info'),
    }

    result = {
        'findings': findings,
        'summary': summary
    }

    # Output
    if args.format == 'json':
        output = json.dumps(result, indent=2)
    elif args.format == 'github':
        output = format_github_review(result)
    else:
        output = format_text_review(result)

    if args.output:
        Path(args.output).write_text(output)
    else:
        print(output)


def format_text_review(result: Dict) -> str:
    """Format as human-readable text."""
    lines = []
    for f in result['findings']:
        lines.append(f"[{f['severity'].upper()}] {f['file']}:{f['line']} - {f['rule']}: {f['message']}")
        if f['suggestion']:
            lines.append(f"  Suggestion: {f['suggestion']}")
    if not lines:
        lines.append("No findings.")
    lines.append(f"\nSummary: {result['summary']['block']} block, {result['summary']['warn']} warn, {result['summary']['info']} info")
    return '\n'.join(lines)


def format_github_review(result: Dict) -> str:
    """Format as GitHub PR review comments."""
    # This would generate GitHub review comment format
    return json.dumps(result, indent=2)


if __name__ == '__main__':
    main()