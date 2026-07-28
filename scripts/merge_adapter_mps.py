#!/usr/bin/env python3
"""Merge LoRA adapter into base model on Apple Silicon (MPS) and export to GGUF.

This replaces scripts/merge_and_export.py for non-CUDA hosts. Loads the adapter
reported by `~/.cache/huggingface/hub/models--moinonin--defiqwen25coder` on top of
the fp16 Qwen2.5-Coder-7B-Instruct base, saves a merged 16-bit HF snapshot, then
invokes llama.cpp's convert_hf_to_gguf.py to emit a q4_k_m GGUF for Ollama.

Output:
    models/qwen2.5-coder-7b-specforge-mps/merged/   (HF model dir)
    models/qwen2.5-coder-7b-specforge-mps/*.gguf     (GGUF for Ollama)
    models/qwen2.5-coder-7b-specforge-mps/Modelfile  (Ollama Modelfile)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent

HF_CACHE = (Path.home() / ".cache" / "huggingface" / "hub"
            / "models--moinonin--defiqwen25coder" / "snapshots")
BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen2.5-coder-7b-specforge-mps"
MERGED_DIR = OUTPUT_DIR / "merged"

CONVERT_SCRIPT = shutil.which("convert_hf_to_gguf.py") or "/opt/homebrew/bin/convert_hf_to_gguf.py"
GGUF_QUANTS = ["q4_k_m"]   # q8_0 optional, adds 8GB; skip by default for eval


def find_adapter_dir() -> Path:
    if not HF_CACHE.exists():
        sys.exit(f"❌ Adapter snapshot dir missing: {HF_CACHE}")
    snaps = [p for p in HF_CACHE.iterdir() if (p / "adapter_config.json").exists()]
    if not snaps:
        sys.exit(f"❌ No snapshot with adapter_config.json under {HF_CACHE}")
    if len(snaps) > 1:
        snaps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        print(f"⚠️  Multiple snapshots, using newest: {snaps[0].name}")
    return snaps[0]


def run_cmd(cmd: str, desc: str, cwd: Path | None = None) -> bool:
    print(f"\n🔄 {desc}\n   $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ {desc} FAILED (exit {result.returncode})")
        if result.stdout.strip():
            print("stdout:", result.stdout[-2000:])
        if result.stderr.strip():
            print("stderr:", result.stderr[-2000:])
        return False
    print(f"✅ {desc} done")
    return True


def main():
    adapter_dir = find_adapter_dir()
    print(f"📍 Adapter:    {adapter_dir}")
    print(f"📍 Base model: {BASE_MODEL}")
    print(f"📍 Output:     {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ----- 1. Load base in fp16 on CPU (M1 16GB unified memory rejects 14GB MPS buffer).
    # Merging is pure weight arithmetic + save — no forward pass needed, so CPU is fine.
    print("\n🧠 Loading base model in fp16 on CPU (no forward pass needed for merge) ...")
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16, low_cpu_mem_usage=True,
    )

    print("🧩 Attaching LoRA adapter ...")
    model = PeftModel.from_pretrained(base, str(adapter_dir))
    print("🔗 Merging adapter weights into base ...")
    model = model.merge_and_unload()

    print(f"💾 Saving merged HF model to {MERGED_DIR} ...")
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(MERGED_DIR, safe_serialization=True)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    # transformers 5.x sticks a torch.dtype in the tokenizer config that json
    # can't serialize; coerce it to str. Then save + port the adapter's chat template.
    tok = AutoTokenizer.from_pretrained(str(adapter_dir))
    tok.save_pretrained(MERGED_DIR)
    adapter_template = adapter_dir / "chat_template.jinja"
    if adapter_template.exists():
        shutil.copy(adapter_template, MERGED_DIR / "chat_template.jinja")
        print(f"   copied chat_template.jinja from adapter")

    # Free Python refs before llama.cpp reads the dump
    del model
    del base
    import gc
    gc.collect()

    # ----- 2. Convert to GGUF -----
    if not Path(CONVERT_SCRIPT).exists():
        sys.exit(f"❌ convert_hf_to_gguf.py not found at {CONVERT_SCRIPT}")

    gguf_paths: list[Path] = []
    for quant in GGUF_QUANTS:
        gguf_path = OUTPUT_DIR / f"qwen2.5-coder-7b-specforge-{quant}.gguf"
        cmd = (f'"{CONVERT_SCRIPT}" --outfile "{gguf_path}" '
               f'--outtype {quant} "{MERGED_DIR}"')
        if not run_cmd(cmd, f"GGUF export ({quant})"):
            sys.exit(f"❌ GGUF conversion ({quant}) failed")
        gguf_paths.append(gguf_path)

    # ----- 3. Write Ollama Modelfile -----
    primary_gguf = gguf_paths[0]
    modelfile_path = OUTPUT_DIR / "Modelfile"
    modelfile = f"""FROM {primary_gguf}

TEMPLATE """ + '"""' + """{{- if .Suffix }}<|fim_prefix|>{{ .Prompt }}<|fim_suffix|>{{ .Suffix }}<|fim_middle|>
{{- else if .Messages }}
{{- range $i, $_ := .Messages }}
{{- if eq .Role "system" }}<|im_start|>system
{{ .Content }}<|im_end|>
{{- else if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{- else if eq .Role "assistant" }}<|im_start|>assistant
{{ .Content }}<|im_end|>
{{- end }}
{{- end }}<|im_start|>assistant
{{- else }}<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
{{- end }}""" + '"""' + """

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
PARAMETER temperature 0.2
PARAMETER num_predict 2048
"""
    modelfile_path.write_text(modelfile)
    print(f"\n📝 Modelfile written to {modelfile_path}")
    print("\n🚀 Next step:")
    print(f"   ollama create specforge -f {modelfile_path}")
    print(f"   make eval-model")


if __name__ == "__main__":
    main()
