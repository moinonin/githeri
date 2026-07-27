#!/usr/bin/env python3
import argparse
from typing import Optional

def run_pipeline(provider: str, cloud_model: Optional[str] = None):
    if provider == 'ollama':
        print(f'Running pipeline with ollama model: {cloud_model}')
    elif provider == 'openrouter':
        print(f'Running pipeline with openrouter model: {cloud_model}')
    else:
        raise ValueError('Invalid provider. Choose from ollama or openrouter.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the pipeline with a specified provider and cloud model.')
    parser.add_argument('--provider', type=str, choices=['ollama', 'openrouter'], required=True, help='The provider to use for scoring.')
    parser.add_argument('--cloud-model', type=str, help='The cloud model to use with the provider.')
    args = parser.parse_args()
    run_pipeline(args.provider, args.cloud_model)