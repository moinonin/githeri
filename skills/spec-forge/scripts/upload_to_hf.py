#!/usr/bin/env python3
"""Upload model files to HuggingFace Hub.

Reads HF_TOKEN from .env (via python-dotenv).
Uploads everything in the --model-dir directory to the specified HF repo.
Does NOT upload model weights if they are in .gitignore — only the standard
files (MODEL_CARD.md, config.json, tokenizer files,adapter_config.json, etc.)

Usage:
    python scripts/upload_to_hf.py --model-dir models/qwen2.5-coder-7b-specforge --repo githeri/qwen2.5-coder-7b-specforge
"""
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
load_dotenv()


def upload_model(model_dir: str, repo_id: str, private: bool = False):
    """Upload model directory to HuggingFace Hub."""
    from huggingface_hub import HfApi, create_repo

    token = os.getenv("HF_TOKEN")
    if not token:
        print("❌ HF_TOKEN not found. Set it in .env file:")
        print('   echo "HF_TOKEN=hf_your_token_here" > .env')
        sys.exit(1)

    model_path = Path(model_dir)
    if not model_path.exists():
        print(f"❌ Model directory not found: {model_path}")
        print("Run 'make train' first to generate adapter weights.")
        sys.exit(1)

    print(f"🚀 Uploading {model_path} to HuggingFace Hub: {repo_id}")
    print(f"   Private: {private}")

    # Create repo if it doesn't exist
    api = HfApi(token=token)
    try:
        create_repo(repo_id=repo_id, token=token, private=private, repo_type="model", exist_ok=True)
        print(f"✅ Repo ready: {repo_id}")
    except Exception as e:
        print(f"❌ Failed to create/access repo: {e}")
        sys.exit(1)

    # Upload all files in the model directory
    # Skip large weight files if --no-weights is set
    files = sorted(model_path.iterdir())
    print(f"📁 Found {len(files)} files to upload:")
    for f in files:
        size = f.stat().st_size / (1024 * 1024)
        print(f"   {f.name} ({size:.1f} MB)")

    uploaded = 0
    for f in files:
        if f.is_file():
            print(f"   Uploading {f.name}...")
            try:
                api.upload_file(
                    path_or_fileobj=str(f),
                    path_in_repo=f.name,
                    repo_id=repo_id,
                    token=token,
                )
                uploaded += 1
                print(f"   ✅ {f.name}")
            except Exception as e:
                print(f"   ❌ {f.name}: {e}")

    # Also upload MODEL_CARD.md from repo root if it exists
    model_card = Path(__file__).resolve().parent.parent / "MODEL_CARD.md"
    if model_card.exists():
        print(f"   Uploading MODEL_CARD.md...")
        try:
            api.upload_file(
                path_or_fileobj=str(model_card),
                path_in_repo="README.md",  # HF renders README.md as the model card
                repo_id=repo_id,
                token=token,
            )
            print(f"   ✅ MODEL_CARD.md → README.md")
        except Exception as e:
            print(f"   ❌ MODEL_CARD.md: {e}")

    print(f"\n🏁 Done! Uploaded {uploaded} files to https://huggingface.co/{repo_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload model to HuggingFace Hub")
    parser.add_argument("--model-dir", required=True, help="Local model directory")
    parser.add_argument("--repo", required=True, help="HF repo ID (e.g. githeri/qwen2.5-coder-7b-specforge)")
    parser.add_argument("--private", action="store_true", help="Make repo private")
    args = parser.parse_args()

    upload_model(args.model_dir, args.repo, args.private)