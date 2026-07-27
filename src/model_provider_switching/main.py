# Import necessary libraries
import argparse
from typing import Optional

# Define the main function
def main(provider: Optional[str] = None, cloud_model: Optional[str] = None):
    parser = argparse.ArgumentParser(description="Run pipeline with model provider")
    parser.add_argument("--provider", type=str, choices=["ollama", "openrouter"], help="Model provider")
    parser.add_argument("--cloud-model", type=str, help="Cloud model")
    args = parser.parse_args()

    if args.provider == 'ollama':
        # Logic for Ollama
        print(f"Running with Ollama and model: {args.cloud_model}")
    elif args.provider == 'openrouter':
        # Logic for OpenRouter
        print(f"Running with OpenRouter and model: {args.cloud_model}")
    else:
        parser.print_help()
        exit(1)

if __name__ == "__main__":
    main()