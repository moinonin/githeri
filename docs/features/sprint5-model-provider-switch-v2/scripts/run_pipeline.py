#!/usr/bin/env python3

import argparse
import os

def main():
    parser = argparse.ArgumentParser(description='Run pipeline with specified provider and model')
    parser.add_argument('--provider', choices=['ollama', 'openrouter'], required=True, help='Model provider (ollama or openrouter)')
    parser.add_argument('--cloud-model', type=str, required=True, help='Cloud model to use')

    args = parser.parse_args()

    if args.provider == 'ollama':
        print('Using Ollama provider with model:', args.cloud_model)
    elif args.provider == 'openrouter':
        print('Using OpenRouter provider with model:', args.cloud_model)

if __name__ == '__main__':
    main()