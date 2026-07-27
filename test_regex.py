import re

# Test the actual goal lines
line1 = '- **L1:** `test -f skills/software-development/ci-cd-integration/SKILL.md && grep -q -- "ci-cd-integration" skills/software-development/ci-cd-integration/SKILL.md` FAIL ✅'
line2 = '- **L2:** `test -f .github/workflows/autonomous.yml && grep -q -- "autonomous" .github/workflows/autonomous.yml` → **PASS** ✅'

# Format 1: command FAIL/PASS ✅
p1 = r'-\s+\*\*(L\d+):?\s+\`([^\`]+)\`\s+(PASS|FAIL)\s*✅'
m = re.search(p1, line1)
print('Format 1 line1:', m)
if m:
    print('Groups:', m.groups())

m = re.search(p1, line2)
print('Format 1 line2:', m)

# Format 2: command → **PASS/FAIL** ✅
p2 = r'-\s+\*\*(L\d+):?\s+\`([^\`]+)\`\s*→\s*\*\*(PASS|FAIL)\*\*\s*✅'
m = re.search(p2, line1)
print('Format 2 line1:', m)

m = re.search(p2, line2)
print('Format 2 line2:', m)
if m:
    print('Groups:', m.groups())