#!/usr/bin/env python

import argparse

parser = argparse.ArgumentParser(description='Run pipeline with model provider')
parser.add_argument('--provider', choices=['ollama', 'openrouter'], required=True, help='Model provider')
parser.add_argument('--cloud-model', required=True, help='Cloud model name')
args = parser.parse_args()

print(f'Provider: {args.provider}, Cloud Model: {args.cloud_model}')