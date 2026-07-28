#!/usr/bin/env python3
"""
Automated pipeline to merge a LoRA adapter into a base model and export to GGUF for Ollama.

Usage:
    python scripts/merge_and_export_automated.py \\
        --base-model-path /path/to/base/model \\
        --adapter-path /path/to/adapter \\
        --output-dir /path/to/output \\
        [--quant q4_k_m|q8_0] \\
        [--force] \\
        [--modelfile-name specforge]
"""

import os
import shutil
import subprocess
import sys
import argparse
from pathlib import Path

# --------------------------- Helper Functions ---------------------------

def run_cmd(cmd: str, description: str, cwd: Path | None = None) -> bool:
    print(f"\n🔄 {description}")
    print(f"   Command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ {description} FAILED")
        print(f"   stderr: {result.stderr.strip()[-1000:]}")
        return False
    print(f"✅ {description} completed")
    if result.stdout.strip():
        print("   stdout:", result.stdout.strip()[:200])
    return True

def merge_adapter(base_dir: Path, adapter_dir: Path, merged_dir: Path) -> bool:
    print(f"🧠 Loading base model from {base_dir} (CPU, fp16)...")
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        base = AutoModelForCausalLM.from_pretrained(
            str(base_dir), torch_dtype=torch.float16, low_cpu_mem_usage=True
        )
        tokenizer = AutoTokenizer.from_pretrained(str(base_dir))
    except Exception as e:
        print(f"❌ Failed to load base model: {e}")
        return False

    print("🧩 Attaching LoRA adapter...")
    try:
        from peft import PeftModel
        model = PeftModel.from_pretrained(base, str(adapter_dir))
        model = model.merge_and_unload()
    except Exception as e:
        print(f"❌ Failed to attach adapter: {e}")
        return False

    print(f"💾 Saving merged model to {merged_dir}...")
    merged_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(merged_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_dir))

    # Copy adapter-specific files
    adapter_template = adapter_dir / "chat_template.jinja"
    if adapter_template.exists():
        shutil.copy(adapter_template, merged_dir / "chat_template.jinja")
        print("   copied chat_template.jinja")
    
    for fname in ["tokenizer.json", "vocab.json", "merges.txt", "special_tokens_map.json", "added_tokens.json", "tokenizer_config.json"]:
        src = adapter_dir / fname
        if src.exists():
            shutil.copy(src, merged_dir / fname)
    
    del model
    import gc
    gc.collect()
    return True

def convert_to_gguf(merged_dir: Path, output_dir: Path, quant: str) -> bool:
    convert_script = "/opt/homebrew/bin/convert_hf_to_gguf.py"
    if not shutil.which(convert_script):
        print("❌ convert_hf_to_gguf.py not found in PATH. Install llama.cpp first.")
        return False

    gguf_path = output_dir / f"qwen2.5-coder-7b-specforge-{quant}.gguf"
    cmd = [
        sys.executable,
        convert_script,
        "--outfile", str(gguf_path),
        "--outtype", quant,
        str(merged_dir)
    ]
    if not run_cmd(" ".join(cmd), f"GGUF conversion ({quant})"):
        return False

    # Also create q8_0 version
    gguf_q8 = output_dir / f"qwen2.5-coder-7b-specforge-q8_0.gguf"
    cmd_q8 = [
        sys.executable,
        convert_script,
        "--outfile", str(gguf_q8),
        "--outtype", "q8_0",
        str(merged_dir)
    ]
    if not run_cmd(" ".join(cmd_q8), "GGUF conversion (q8_0)", cwd=merged_dir):
        return False

    return True

def create_modelfile(gguf_path: Path, output_dir: Path, model_name: str) -> bool:
    modelfile_path = output_dir / f"Modelfile_{model_name}.txt"
    template = """{{- if .Suffix }}<|fim_prefix|>{{ .Prompt }}<|fim_suffix|>{{ .Suffix }}<|fim_middle|>
{{- else if .Messages }}
{{- range $i, $_ := .Messages }}
{{- if eq .Role "system" }}  system
{{ .Content }} 
{{- else if eq .Role "user" }}  user
{{ .Content }} 
{{- else if eq .Role "assistant" }}  assistant
{{ .Content }} 
{{- end }}
{{- end }} 
{{- else }}  user
{{ .Prompt }} 
  assistant
{{- end }}"""
    
    modelfile_content = f"""FROM {gguf_path.name}

TEMPLATE {template}

PARAMETER stop "  "
PARAMETER stop "  "
PARAMETER temperature 0.2
PARAMETER num_predict 2048
"""
    modelfile_path.write_text(modelfile_content)
    print(f"📝 Modelfile created at {modelfile_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into base model and export to GGUF for Ollama")
    parser.add_argument("--base-model-path", required=True, help="Path to base model directory")
    parser.add_argument("--adapter-path", required=True, help="Path to adapter directory")
    parser.add_argument("--output-dir", required=True, help="Directory where merged model and GGUF will be saved")
    parser.add_argument("--quant", default="q4_k_m", help="GGUF quantization type (default: q4_k_m)")
    parser.add_argument("--force", action="store_true", help="Force re-run even if outputs exist")
    parser.add_argument("--modelfile-name", default="specforge", help="Name for the Ollama model")

    args = parser.parse_args()

    base_dir = Path(args.base_model_path).resolve()
    adapter_dir = Path(args.adapter_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    quant = args.quant
    force = args.force
    model_name = args.modelfile_name

    if not base_dir.exists():
        sys.exit(f"❌ Base model directory does not exist: {base_dir}")
    if not adapter_dir.exists():
        sys.exit(f"❌ Adapter directory does not exist: {adapter_dir}")

    merged_dir = output_dir / "merged"
    gguf_path = output_dir / f"qwen2.5-coder-7b-specforge-{quant}.gguf"
    modelfile_path = output_dir / f"Modelfile_{model_name}.txt"

    if not args.force:
        if (merged_dir / "model.safetensors").exists() and gguf_path.exists():
            print("✅ Merged model and GGUF already exist – skipping steps.")
            return

    output_dir.mkdir(parents=True, exist_ok=True)
    merged_dir = output_dir / "merged"

    # Step 1: Merge adapter into base model
    if not (merged_dir / "model.safetensors").exists() or force:
        print("🔗 Merging adapter into base model...")
        if not merge_adapter(base_dir, adapter_dir, merged_dir):
            sys.exit(1)

    # Step 2: Convert to GGUF
    if not gguf_path.exists() or force:
        print("📦 Converting to GGUF...")
        if not convert_to_gguf(merged_dir, output_dir, quant):
            sys.exit(1)

    # Step 3: Create Modelfile for Ollama
    if not modelfile_path.exists() or force:
        print("📝 Creating Ollama Modelfile...")
        if not create_modelfile(gguf_path, output_dir, model_name):
            sys.exit(1)

    print("\n✅ Export complete!")
    print(f"   Merged model: {merged_dir}")
    print(f"   GGUF file: {gguf_path}")
    print(f"   Modelfile: {modelfile_path}")
    print("\n🚀 Next steps:")
    print(f"   ollama create {model_name} -f {modelfile_path}")
    print(f"   ollama run {model_name}")

if __name__ == "__main__":
    import torch
    main()