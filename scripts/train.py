#!/usr/bin/env python3
"""
LoRA fine-tuning script for qwen2.5-coder-7b-instruct on Spec-Forge task.

Requires:
- unsloth (pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git")
- trl, peft, accelerate, bitsandbytes
- CUDA GPU with 8GB+ VRAM (gradient checkpointing for 8GB cards)

Output: models/qwen2.5-coder-7b-specforge/ (adapter weights)
"""
import os
os.environ["UNSLOTH_USE_PYTORCH"] = "1"
os.environ["UNSLOTH_FORCE_PYTORCH"] = "1"

import json
import sys
import torch
from pathlib import Path

# Force PyTorch backend BEFORE importing unsloth
os.environ["UNSLOTH_USE_PYTORCH"] = "1"
os.environ["UNSLOTH_FORCE_PYTORCH"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "training_data_chat.jsonl"
OUTPUT_DIR = PROJECT_ROOT / "models" / "qwen2.5-coder-7b-specforge"

# Check if training data exists
if not DATA_FILE.exists():
    print(f"❌ Training data not found: {DATA_FILE}")
    print("Run 'make convert-chat' first to generate training_data_chat.jsonl")
    exit(1)

# Import after path setup
try:
    from unsloth import FastLanguageModel
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from datasets import load_dataset
    from transformers import TrainingArguments
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Install with: pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\" trl peft accelerate bitsandbytes")
    exit(1)

# Model config
MODEL_NAME = "unsloth/Qwen2.5-Coder-7B-Instruct"
MAX_SEQ_LENGTH = 2048  # Match training data context

# Force PyTorch backend (not MLX) on all platforms
os.environ["UNSLOTH_USE_PYTORCH"] = "1"

# On MPS (Apple Silicon), bfloat16 not supported - use float16
# On CUDA with bf16 support, use bfloat16; otherwise float16
if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
    DTYPE = torch.bfloat16
elif torch.backends.mps.is_available():
    DTYPE = torch.float16  # MPS supports float16, not bfloat16
else:
    DTYPE = torch.float16

LOAD_IN_4BIT = True
# LoRA config
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.1
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

# Training config
BATCH_SIZE = 1  # Per device
GRAD_ACCUM = 4  # Effective batch = 1 * 4 = 4
EPOCHS = 3
LEARNING_RATE = 2e-4
WARMUP_RATIO = 0.1
WEIGHT_DECAY = 0.01
LOGGING_STEPS = 10
SAVE_STEPS = 100
SEED = 42

print(f"📊 Config: model={MODEL_NAME}, seq_len={MAX_SEQ_LENGTH}, 4bit={LOAD_IN_4BIT}")
print(f"📊 LoRA: r={LORA_R}, alpha={LORA_ALPHA}, dropout={LORA_DROPOUT}")
print(f"📊 Training: epochs={EPOCHS}, batch={BATCH_SIZE}, grad_accum={GRAD_ACCUM}, lr={LEARNING_RATE}")

# Load model
print("🔄 Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=DTYPE,
    load_in_4bit=LOAD_IN_4BIT,
)

# Add LoRA adapters
print("🔧 Adding LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=TARGET_MODULES,
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",  # Memory efficient
    random_state=SEED,
    use_rslora=False,
    loftq_config=None,
)

# Load dataset
print("📂 Loading dataset...")
dataset = load_dataset("json", data_files=str(DATA_FILE), split="train")

# Format for chat template
def format_chat(example):
    messages = example["messages"]
    # Apply chat template
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}

print("📝 Formatting dataset...")
dataset = dataset.map(format_chat, remove_columns=dataset.column_names)

# Split train/eval (90/10)
split = dataset.train_test_split(test_size=0.1, seed=SEED)
train_dataset = split["train"]
eval_dataset = split["test"]

print(f"📊 Train: {len(train_dataset)}, Eval: {len(eval_dataset)}")

# Training arguments
training_args = TrainingArguments(
    output_dir=str(OUTPUT_DIR),
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    warmup_ratio=WARMUP_RATIO,
    num_train_epochs=EPOCHS,
    learning_rate=LEARNING_RATE,
    weight_decay=WEIGHT_DECAY,
    logging_steps=LOGGING_STEPS,
    save_steps=SAVE_STEPS,
    eval_steps=SAVE_STEPS,
    evaluation_strategy="steps",
    save_strategy="steps",
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    greater_is_better=False,
    fp16=(DTYPE == torch.float16),
    bf16=(DTYPE == torch.bfloat16),
    optim="adamw_8bit" if LOAD_IN_4BIT else "adamw_torch",
    lr_scheduler_type="cosine",
    seed=SEED,
    report_to="none",  # Disable wandb/tensorboard
    remove_unused_columns=False,
    dataloader_pin_memory=False,
    dataloader_num_workers=0,
)

# Trainer
print("🏋️  Creating trainer...")
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    max_seq_length=MAX_SEQ_LENGTH,
    args=training_args,
    packing=False,  # Don't pack sequences (preserves chat boundaries)
)

# Train
print("🚀 Starting training...")
trainer.train()

# Save final model
print("💾 Saving adapter...")
trainer.save_model()
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"✅ Training complete! Adapter saved to {OUTPUT_DIR}")
print(f"📊 Final eval loss: {trainer.state.log_history[-1].get('eval_loss', 'N/A')}")

# Quick test
print("\n🧪 Quick inference test...")
FastLanguageModel.for_inference(model)
prompt = "Add a POST /health endpoint that returns 200 OK with status: healthy"
messages = [
    {"role": "system", "content": "You are a precise specification generator. Output ONLY a YAML document."},
    {"role": "user", "content": prompt},
]
inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
outputs = model.generate(inputs, max_new_tokens=512, temperature=0.2, do_sample=True)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(f"Prompt: {prompt}")
print(f"Response: {response}")