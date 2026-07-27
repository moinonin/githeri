#!/usr/bin/env python3
"""
Security Scanner - Detects secrets, vulnerabilities, license issues
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any


class SecurityScanner:
    def __init__(self):
        self.findings = []

        # Secret patterns
        self.secret_patterns = [
            ('api_key', r'(api[_-]?key|apikey)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{20,}[\'"]'),
            ('secret_key', r'(secret[_-]?key|secretkey)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{20,}[\'"]'),
            ('password', r'(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{8,}[\'"]'),
            ('token', r'(token|access[_-]?token)\s*[=:]\s*["\'][a-zA-Z0-9_\-]{20,}[\'"]'),
            ('aws_key', r'(aws[_-]?access[_-]?key|aws[_-]?secret[_-]?key)\s*[=:]\s*["\'][A-Z0-9/+=]{20,}[\'"]'),
            ('openai_key', r'sk-[a-zA-Z0-9]{20,}'),
            ('github_token', r'gh[pousr]_[a-zA-Z0-9]{20,}'),
            ('slack_token', r'xox[baprs]-[a-zA-Z0-9-]{10,}'),
            ('generic_secret', r'(secret|credential)\s*[=:]\s*["\'][^"\']{10,}[\'"]'),
        ]

        # Vulnerability patterns
        self.vuln_patterns = [
            ('sql_injection', r'(execute|query|raw)\s*\([^)]*%[^)]*\)', 'Possible SQL injection via string formatting'),
            ('command_injection', r'(subprocess\.(run|Popen)|os\.system|os\.popen)\s*\([^)]*\+', 'Possible command injection'),
            ('path_traversal', r'(open|read|write)\s*\([^)]*\.\./', 'Possible path traversal'),
            ('eval_injection', r'\b(eval|exec)\s*\(', 'Use of eval/exec - code injection risk'),
            ('pickle_load', r'pickle\.loads?\s*\(', 'Pickle deserialization - arbitrary code execution'),
            ('yaml_load', r'yaml\.load\s*\([^)]*Loader=yaml\.Loader', 'Unsafe YAML load - use safe_load'),
        ]

        # License patterns (problematic licenses)
        self.license_patterns = [
            ('AGPL', r'AGPL|GNU Affero General Public License', 'Copyleft - may require source disclosure'),
            ('GPL', r'\bGPL\b(?!-compatible)', 'Copyleft - may require source disclosure'),
            ('LGPL', r'\bLGPL\b', 'Weak copyleft - linking restrictions'),
        ]

    def add_finding(self, file: str, line: int, severity: str, category: str, rule: str, message: str, context: str = ""):
        self.findings.append({
            "file": file,
            "line": line,
            "severity": severity,
            "category": category,
            "rule": rule,
            "message": message,
            "context": context[:200]
        })

    def scan_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan a single file for security issues."""
        findings = []

        try:
            content = file_path.read_text(errors='ignore')
        except Exception:
            return findings

        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            # Scan for secrets
            for rule_name, pattern in self.secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.add_finding(str(file_path), i, 'block', 'secrets', rule_name,
                        f"Potential {rule_name.replace('_', ' ')} detected",
                        line.strip())

            # Scan for vulnerabilities
            for rule_name, pattern, msg in self.vuln_patterns:
                if re.search(pattern, line):
                    self.add_finding(str(file_path), i, 'warn', 'vulnerabilities', rule_name,
                        msg,
                        line.strip())

        return self.findings

    def scan_license_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Scan license file for problematic licenses."""
        findings = []
        try:
            content = file_path.read_text(errors='ignore').lower()
        except Exception:
            return findings

        for rule_name, pattern, msg in self.license_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                self.add_finding(str(file_path), 1, 'warn', 'license', rule_name,
                    f"License contains {rule_name}: {msg}",
                    file_path.name)
        return findings

    def scan_directory(self, path: Path, include_licenses: bool = True) -> Dict[str, Any]:
        """Scan all files in directory."""
        all_findings = []

        for file_path in path.rglob('*'):
            if not file_path.is_file():
                continue

            # Skip binary files, hidden dirs, venv, build
            if any(part.startswith('.') for part in file_path.parts):
                continue
            if '__pycache__' in file_path.parts:
                continue
            if '.venv' in file_path.parts or 'venv' in file_path.parts:
                continue
            if 'build' in file_path.parts or 'dist' in file_path.parts:
                continue
            if file_path.suffix in ('.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2'):
                continue

            # Scan for secrets and vulnerabilities
            all_findings.extend(self.scan_file(file_path))

            # Scan license files
            if include_licenses and file_path.name.lower() in ('license', 'license.txt', 'license.md', 'copying', 'copying.txt'):
                all_findings.extend(self.scan_license_file(file_path))

        self.findings = all_findings

        # Summary
        block_count = sum(1 for f in all_findings if f['severity'] == 'block')
        warn_count = sum(1 for f in all_findings if f['severity'] == 'warn')
        info_count = sum(1 for f in all_findings if f['severity'] == 'info')

        return {
            'findings': all_findings,
            'summary': {
                'total': len(all_findings),
                'block': block_count,
                'warn': warn_count,
                'info': info_count
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Security Scanner")
    parser.add_argument('--path', default='.', help="Path to scan (default: .)")
    parser.add_argument('--rules', default='secrets,vulnerabilities,licenses', help="Rules to run")
    parser.add_argument('--format', choices=['json', 'text'], default='text', help="Output format")
    parser.add_argument('--strict', action='store_true', help="Exit with error on findings")
    args = parser.parse_args()

    scanner = SecurityScanner()
    result = scanner.scan_directory(Path(args.path))

    if args.format == 'json':
        print(json.dumps(result, indent=2))
    else:
        if not result['findings']:
            print("✅ No security issues found")
            return

        for f in result['findings']:
            icon = '🔴' if f['severity'] == 'block' else '🟡' if f['severity'] == 'warn' else '🔵'
            print(f"{icon} [{f['severity'].upper()}] {f['file']}:{f['line']} ({f['category']}/{f['rule']}): {f['message']}")
            if f['context']:
                print(f"    Context: {f['context'][:100]}")

        print(f"\nSummary: {result['summary']['total']} findings ({result['summary']['block']} block, {result['summary']['warn']} warn)")

    if args.strict and result['summary']['block'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()