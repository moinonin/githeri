#!/usr/bin/env python3
"""
Pattern Enforcement - Checks code against project patterns.
"""

import argparse
import json
import re
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any


class PatternEnforcer:
    """Enforces project patterns from .hermes/patterns/."""

    def __init__(self, patterns_dir: Path):
        self.patterns_dir = patterns_dir
        self.patterns = {}
        self.load_patterns()

    def load_patterns(self):
        """Load all pattern YAML files."""
        for pattern_file in self.patterns_dir.glob('*.yaml'):
            with open(pattern_file) as f:
                self.patterns[pattern_file.stem] = yaml.safe_load(f)

    def check_naming(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Check naming conventions."""
        violations = []
        naming = self.patterns.get('naming', {})

        # Check function names
        if 'functions' in naming:
            func_pattern = naming['functions'].get('regex', '^[a-z_][a-z0-9_]*$')
            for match in re.finditer(r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', content):
                func_name = match.group(1)
                if not re.match(func_pattern, func_name):
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append({
                        'file': str(file_path),
                        'line': line_num,
                        'type': 'naming',
                        'rule': 'function_naming',
                        'message': f"Function '{func_name}' doesn't match snake_case pattern",
                        'severity': 'warn'
                    })

        # Check class names
        if 'classes' in naming:
            class_pattern = naming['classes'].get('regex', '^[A-Z][a-zA-Z0-9]*$')
            for match in re.finditer(r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]', content):
                class_name = match.group(1)
                if not re.match(class_pattern, class_name):
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append({
                        'file': str(file_path),
                        'line': line_num,
                        'type': 'naming',
                        'rule': 'class_naming',
                        'message': f"Class '{class_name}' doesn't match PascalCase pattern",
                        'severity': 'warn'
                    })

        # Check constants
        if 'constants' in naming:
            const_pattern = naming['constants'].get('regex', '^[A-Z][A-Z0-9_]*$')
            for match in re.finditer(r'^([A-Z][A-Z0-9_]*)\s*=', content, re.MULTILINE):
                const_name = match.group(1)
                if not re.match(const_pattern, const_name):
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append({
                        'file': str(file_path),
                        'line': line_num,
                        'type': 'naming',
                        'rule': 'constant_naming',
                        'message': f"Constant '{const_name}' doesn't match SCREAMING_SNAKE_CASE pattern",
                        'severity': 'warn'
                    })

        return violations

    def check_imports(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Check import ordering and banned imports."""
        violations = []
        imports = self.patterns.get('naming', {}).get('imports', {})
        banned = imports.get('banned', [])

        # Check for banned imports
        for banned_import in banned:
            if banned_import in content:
                for i, line in enumerate(content.split('\n'), 1):
                    if banned_import in line:
                        violations.append({
                            'file': str(file_path),
                            'line': i,
                            'type': 'imports',
                            'rule': 'banned_import',
                            'message': f"Banned import detected: {banned_import}",
                            'severity': 'block'
                        })

        return violations

    def check_structure(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Check file structure."""
        violations = []
        structure = self.patterns.get('naming', {}).get('structure', {})
        max_depth = structure.get('max_depth', 4)

        # Check depth
        depth = len(file_path.parts) - 1  # relative to project root
        if depth > max_depth:
            violations.append({
                'file': str(file_path),
                'line': 1,
                'type': 'structure',
                'rule': 'max_depth',
                'message': f"File depth ({depth}) exceeds maximum ({max_depth})",
                'severity': 'warn'
            })

        return violations

    def check_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Check a single file against all patterns."""
        if not file_path.is_file():
            return []

        if file_path.suffix != '.py':
            return []

        try:
            with open(file_path) as f:
                content = f.read()
        except Exception:
            return []

        violations = []
        violations.extend(self.check_naming(file_path, content))
        violations.extend(self.check_imports(file_path, content))
        violations.extend(self.check_structure(file_path, content))

        return violations

    def check_directory(self, path: Path, strict: bool = False) -> Dict[str, Any]:
        """Check all Python files in directory."""
        all_violations = []

        for py_file in path.rglob('*.py'):
            # Skip hidden dirs, __pycache__, .venv, tests
            if any(part.startswith('.') for part in py_file.parts):
                continue
            if '__pycache__' in py_file.parts:
                continue
            if '.venv' in py_file.parts:
                continue
            if 'test' in py_file.parts and not strict:
                continue

            all_violations.extend(self.check_file(py_file))

        # Summary
        block_count = sum(1 for v in all_violations if v['severity'] == 'block')
        warn_count = sum(1 for v in all_violations if v['severity'] == 'warn')
        info_count = sum(1 for v in all_violations if v['severity'] == 'info')

        return {
            'violations': all_violations,
            'summary': {
                'total': len(all_violations),
                'block': block_count,
                'warn': warn_count,
                'info': info_count
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Enforce code patterns")
    parser.add_argument('--path', default='.', help="Path to check (default: .)")
    parser.add_argument('--patterns', default='.hermes/patterns', help="Patterns directory")
    parser.add_argument('--strict', action='store_true', help="Strict mode (check tests too)")
    parser.add_argument('--format', choices=['json', 'text'], default='text', help="Output format")
    args = parser.parse_args()

    patterns_dir = Path(args.path) / args.patterns
    if not patterns_dir.exists():
        print(f"Patterns directory not found: {patterns_dir}")
        sys.exit(1)

    enforcer = PatternEnforcer(patterns_dir)
    result = enforcer.check_directory(Path(args.path), args.strict)

    if args.format == 'json':
        print(json.dumps(result, indent=2))
    else:
        if not result['violations']:
            print("✅ No pattern violations found")
            return

        for v in result['violations']:
            icon = '🔴' if v['severity'] == 'block' else '🟡'
            print(f"{icon} [{v['severity'].upper()}] {v['file']}:{v['line']} ({v['type']}/{v['rule']}): {v['message']}")

        print(f"\nSummary: {result['summary']['total']} violations ({result['summary']['block']} block, {result['summary']['warn']} warn)")

    if result['summary']['block'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()