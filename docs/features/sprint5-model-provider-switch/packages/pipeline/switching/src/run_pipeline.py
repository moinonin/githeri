# src/run_pipeline.py
import argparse
import os

# Define CLI arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Run pipeline with specified model provider and cloud model')
    parser.add_argument('--provider', choices=['ollama', 'openrouter'], required=True, help='Model provider (ollama or openrouter)')
    parser.add_argument('--cloud-model', required=True, help='Cloud model name')
    return parser.parse_args()

# Load environment variables
def load_env_vars():
    ollama_api_key = os.getenv('OLLAMA_API_KEY')
    openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
    if not (ollama_api_key and openrouter_api_key):
        raise ValueError('Environment variables OLLAMA_API_KEY and OPENROUTER_API_KEY must be set')

# Main function
def main():
    args = parse_args()
    load_env_vars()
    print(f'Running pipeline with provider: {args.provider}, cloud model: {args.cloud_model}')

if __name__ == '__main__':
    main()