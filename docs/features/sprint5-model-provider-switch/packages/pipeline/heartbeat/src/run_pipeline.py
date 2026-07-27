# src/run_pipeline.py
import argparse
import os
from dotenv import load_dotenv

# Load environment variables from .env file
def load_env_vars():
    load_dotenv()

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Run pipeline with specified model provider and cloud model')
    parser.add_argument('--provider', choices=['ollama', 'openrouter'], required=True, help='Model provider (ollama or openrouter)')
    parser.add_argument('--cloud-model', required=True, help='Cloud model name')
    return parser.parse_args()

# Main function to run the pipeline
def main():
    args = parse_args()
    load_env_vars()

    # Example logic based on provider and cloud model
    if args.provider == 'ollama':
        print(f'Running Ollama model: {args.cloud_model}')
        ollama_api_key = os.getenv('OLLAMA_API_KEY')
        if not ollama_api_key:
            raise ValueError('OLLAMA_API_KEY is not set in .env file')
    elif args.provider == 'openrouter':
        print(f'Running OpenRouter model: {args.cloud_model}')
        openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        if not openrouter_api_key:
            raise ValueError('OPENROUTER_API_KEY is not set in .env file')

if __name__ == '__main__':
    main()