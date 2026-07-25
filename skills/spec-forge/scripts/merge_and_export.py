#!/usr/bin/env python3
"""Merge LoRA adapter with base model and export GGUF for Ollama.

Requires:
- llama-cpp-python (for GGUF export)
- huggingface_hub
- unsloth

Input: models/qwen2.5-coder-7b-specforge/ (adapter weights)
Output: models/qwen2.5-coder-7b-specforge-gguf/ (GGUF files)
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_DIR = PROJECT_ROOT / "models" / "qwen2.5-coder-7b-specforge"
BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen2.5-coder-7b-specforge-gguf"


def run_cmd(cmd, description):
    """Run a shell command and return success."""
    print(f"🔄 {description}...")
    print(f"   Command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Failed: {result.stderr}")
        return False
    print(f"✅ {description} done")
    if result.stdout.strip():
        print(f"   Output: {result.stdout.strip()[:200]}")
    return True


def main():
    if not ADAPTER_DIR.exists():
        print("❌ Adapter directory not found. Run 'make train' first.")
        sys.exit(1)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Merge adapter with base model using unsloth/transformers
    print("🔗 Merging adapter with base model...")
    merge_cmd = (
        "python -c \""
        "from unsloth import FastLanguageModel; "
        "model, tokenizer = FastLanguageModel.from_pretrained("
        "model_name='unsloth/Qwen2.5-Coder-7B-Instruct', "
        "max_seq_length=2048, dtype=None, load_in_4bit=True); "
        "model = FastLanguageModel.get_peft_model(model, r=16); "
        f"model.load_adapter('{ADAPTER_DIR}'); "
        f"model.save_pretrained_merged('{OUTPUT_DIR}/merged', tokenizer, save_method='merged_16bit')"
        "\""
    )
    if not run_cmd(merge_cmd, "Merging adapter"):
        sys.exit(1)

    # Export to GGUF using llama.cpp
    print("📦 Exporting to GGUF...")
    gguf_cmd = (
        f"cd /tmp && git clone --depth 1 https://github.com/ggerganov/llama.cpp "
        f"&& cd llama.cpp && make -j$(nproc) "
        f"&& python3 convert_hf_to_gguf.py "
        f"--outfile {OUTPUT_DIR}/qwen2.5-coder-7b-specforge-q4_k_m.gguf "
        f"--outtype q4_k_m "
        f"{OUTPUT_DIR}/merged"
    )
    if not run_cmd(gguf_cmd, "Converting to GGUF (q4_k_m)"):
        print("⚠️  GGUF conversion failed. Try manually:")
        print(f"   cd llama.cpp && python convert_hf_to_gguf.py --outfile {OUTPUT_DIR}/qwen2.5-coder-7b-specforge.gguf {OUTPUT_DIR}/merged")
        sys.exit(1)

    # Also export q8_0 for higher quality
    gguf_cmd_q8 = (
        f"cd /tmp/llama.cpp && python3 convert_hf_to_gguf.py "
        f"--outfile {OUTPUT_DIR}/qwen2.5-coder-7b-specforge-q8_0.gguf "
        f"--outtype q8_0 "
        f"{OUTPUT_DIR}/merged"
    )
    if not run_cmd(gguf_cmd_q8, "Converting to GGUF (q8_0)"):
        print("⚠️  q8_0 conversion failed, but q4_k_m may have succeeded")

    print(f"\n✅ Export complete! GGUF files in {OUTPUT_DIR}:")
    for f in OUTPUT_DIR.glob("*.gguf"):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"   {f.name}: {size_mb:.1f} MB")

    # Create Modelfile for Ollama
    modelfile_path = OUTPUT_DIR / "Modelfile"
    modelfile = f'''FROM {OUTPUT_DIR}/qwen2.5-coder-7b-specforge-q4_k_m.gguf
TEMPLATE "{{{{ if .System }}}}system
{{{{ .System }}}}{{{{ end }}}}
user
{{{{ .Prompt }}}}
assistant
"
PARAMETER stop "user"
PARAMETER stop "assistant"
PARAMETER temperature 0.2
PARAMETER num_predict 2048
'''
    modelfile_path.write_text(modelfile)
    print(f"📝 Modelfile created at {modelfile_path}")
    print(f"\n🚀 To use in Ollama:")
    print(f"   ollama create specforge -f {modelfile_path}")
    print(f"   ollama run specforge")


if __name__ == "__main__":
    main()