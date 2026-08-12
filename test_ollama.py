#!/usr/bin/env python3
import requests
resp = requests.post('http://localhost:11434/api/generate', 
    json={'model': 'specforge-128k:latest', 'prompt': 'test', 'stream': False, 'options': {'temperature': 0.2, 'num_predict': 100}},
    timeout=30)
print(resp.json()['response'][:200])