# packages/pipeline/src/run_pipeline.py
import argparse
from typing import Optional

def main(provider: Optional[str] = None, cloud_model: Optional[str] = None):
    if provider == 'ollama':
        print('Using Ollama model')
    elif provider == 'openrouter':
        print('Using OpenRouter model')
    else:
        print('No provider specified or invalid provider')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run pipeline with different providers and models.')
    parser.add_argument('--provider', choices=['ollama', 'openrouter'], help='Model provider (ollama, openrouter)')
    parser.add_argument('--cloud-model', type=str, help='Cloud model name')
    args = parser.parse_args()
    main(args.provider, args.cloud_model)