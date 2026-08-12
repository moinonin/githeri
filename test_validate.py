#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/nickrotich/Desktop/portfolio/projects/python/ai/githeri/scripts')
from validator import validate_spec

result = validate_spec('task_id: test\nsummary: test\nlocal_goals: []')
print(f'Type: {type(result)}')
print(f'Value: {result}')
print(f'Len: {len(result)}')