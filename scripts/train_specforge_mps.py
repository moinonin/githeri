#!/usr/bin/env python3
"""
LoRA fine-tuning script for qwen2.5-coder-7b-instruct on Spec-Forge task.
Uses Karakana's MPS-compatible training pipeline with conservative profile.

Requires:
- torch, peft, accelerate, bitsandbytes
- CUDA GPU with 8GB+ VRAM (gradient checkpointing for 8GB cards) OR Apple MPS

Output: models/qwen2.5-coder-7b-specforge/ (adapter weights)
"""

import os
import json
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType
from datasets import load_dataset
from tqdm import tqdm
import pandas as pd
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
hf_token = os.getenv("HF_TOKEN")

# Configuration (Conservative Profile from karakana-config.json)
finance_profile = {
    "lambda_sgo": 0.01,
    "loss_module": "probability_kl",
    "ranking_profile": "conservative",
    "max_length": 512,
}

MODEL_ID = os.getenv("KARAKANA_FINANCE_BASE_MODEL", "unsloth/Qwen2.5-Coder-7B-Instruct")
OUTPUT_DIR = os.getenv("KARAKANA_FINANCE_ADAPTER_DIR", "artifacts/checkpoints/specforge_qwen25coder_7b_adapter")
DATASET_ID = os.getenv("KARAKANA_FINANCE_DATASET", "gbharti/finance-alpaca")
DATASET_SPLIT = os.getenv("KARAKANA_FINANCE_DATASET_SPLIT", "train[:200]")
MAX_LENGTH = int(os.getenv("KARAKANA_FINANCE_TRAIN_MAX_LENGTH", "512"))
BATCH_SIZE = int(os.getenv("KARAKANA_FINANCE_TRAIN_BATCH_SIZE", "1"))
EPOCHS = int(os.getenv("KARAKANA_FINANCE_TRAIN_EPOCHS", "10"))
LEARNING_RATE = float(os.getenv("KARAKANA_FINANCE_TRAIN_LR", "1e-4"))
CHECKPOINT_DIR = Path(os.getenv("KARAKANA_FINANCE_CHECKPOINT_DIR", "artifacts/checkpoints/specforge_qwen25coder_7b_adapter_checkpoints"))
EARLY_STOPPING_PATIENCE = int(os.getenv("KARAKANA_FINANCE_EARLY_STOPPING_PATIENCE", "2"))
EARLY_STOPPING_MIN_DELTA = float(os.getenv("KARAKANA_FINANCE_EARLY_STOPPING_MIN_DELTA", "0.0"))
MAX_STEPS_PER_EPOCH = int(os.getenv("KARAKANA_FINANCE_MAX_STEPS_PER_EPOCH", "50"))
USE_GRADIENT_CHECKPOINTING = os.getenv("KARAKANA_FINANCE_GRADIENT_CHECKPOINTING", "1") == "1"
GRG_HARD_STOP = os.getenv("KARAKANA_FINANCE_GRG_HARD_STOP", "0") == "1"

def train():
    # Device selection - prefer MPS on Apple Silicon
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("Using CUDA GPU")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        print("Using Apple MPS")
    else:
        device = torch.device("cpu")
        print("Using CPU")

    # 1. Compact base model
    model_id = MODEL_ID
    print(f"Loading model {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=hf_token)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Use float32 for MPS stability
    dtype = torch.float32

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=dtype,
        low_cpu_mem_usage=True,
        device_map=None,
        token=hf_token,
    )
    model = model.to(device)
    model.config.use_cache = False
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()

    # 2. LoRA setup
    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=8, lora_alpha=32, lora_dropout=0.1,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, peft_config)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Dataset
    dataset = load_dataset(DATASET_ID, split=DATASET_SPLIT, token=hf_token)

    # Filter out short answers
    MIN_OUTPUT_LENGTH = int(os.getenv("KARAKANA_FINANCE_MIN_OUTPUT_LENGTH", "100"))
    dataset = dataset.filter(lambda ex: len(ex.get("output", "").split()) >= MIN_OUTPUT_LENGTH)

    # System prompt for thorough, long-form answers
    TRAINING_SYSTEM_PROMPT = (
        "You are a precise specification generator. Output ONLY a YAML document. "
        "No code, no commentary. Convert the given feature request into a valid "
        "executable specification with task_id, summary, local_goals (with "
        "verification steps), global_goals_refs, and context."
    )

    def format_instruction(example):
        user_content = example["instruction"]
        if example.get("input") and example["input"].strip():
            user_content = f"{user_content}\n\n{example['input']}"
        messages = [
            {"role": "system", "content": TRAINING_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": example["output"]},
        ]
        return {"text": tokenizer.apply_chat_template(messages, tokenize=False)}

    dataset = dataset.map(format_instruction)
    tokenized_dataset = dataset.map(
        lambda x: tokenizer(x["text"], padding="max_length", truncation=True, max_length=MAX_LENGTH),
        batched=True, remove_columns=dataset.column_names
    )
    tokenized_dataset.set_format(type="torch", columns=["input_ids", "attention_mask"])
    dataloader = DataLoader(tokenized_dataset, batch_size=BATCH_SIZE, shuffle=True)

    # Losses & optimiser (Conservative Profile)
    l_sgo = 0.01
    ranking_profile = "conservative"

    # We'll use standard CE + a structural penalty on the outcomes
    from karakana.pytorch import SGOLossModule
    sgo_module = SGOLossModule(
        lambda_sgo=l_sgo,
        metric_key="normalized_structure_term",
        loss_module="probability",
        ranking_profile=ranking_profile
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    grg = GRGController(optimizer, base_lr=LEARNING_RATE, profile="finance_rag")

    # Training loop with Structural Steering
    model.train()
    history = []
    best_epoch_loss = float("inf")
    best_step_loss = float("inf")
    best_step_dir = CHECKPOINT_DIR / "best_step"
    stale_epochs = 0
    grg_stop_seen = False
    grg_stop_events = 0
    if best_step_dir.exists():
        shutil.rmtree(best_step_dir)

    print(f"Starting Spec-Forge Retraining (Lambda={l_sgo})...")
    for epoch in range(EPOCHS):
        pbar = tqdm.tqdm(dataloader, desc=f"Epoch {epoch}")
        epoch_losses = []
        epoch_alphas = []

        for step, batch in enumerate(pbar, start=1):
            if MAX_STEPS_PER_EPOCH and step > MAX_STEPS_PER_EPOCH:
                break

            input_ids, attention_mask = batch["input_ids"].to(device), batch["attention_mask"].to(device)
            labels = input_ids.clone()
            labels[attention_mask == 0] = -100

            optimizer.zero_grad()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            ce_loss = outputs.loss

            # SGO integration
            shift_logits = outputs.logits[:, :-1, :].contiguous()
            shift_labels = labels[:, 1:].contiguous()
            log_probs = torch.log_softmax(shift_logits, dim=-1)
            target_log_probs = torch.gather(log_probs, dim=-1, index=shift_labels.unsqueeze(-1)).squeeze(-1)
            avg_log_prob = torch.mean(log_probs, dim=-1)
            outcomes = (target_log_probs - avg_log_prob) * 2.0

            sgo_loss = sgo_module(outcomes.view(-1))
            total_loss = ce_loss + sgo_loss
            total_loss.backward()
            optimizer.step()

            # REAL-TIME STRUCTURAL STEERING (GRG)
            with torch.no_grad():
                sgo_raw = sgo_module(outcomes.view(-1))
                curr_alpha = max(0.0, min(1.0, 1.0 - (float(sgo_raw.item()) / l_sgo)))
                epoch_alphas.append(curr_alpha)
                stats = grg.step(curr_alpha)

                if grg.should_stop():
                    grg_stop_events += 1
                    if not grg_stop_seen:
                        print("\n[GRG] Structural stop condition detected.")
                        grg_stop_seen = True
                    if GRG_HARD_STOP:
                        print("[GRG] Hard stop enabled; halting training.")
                        break

            history.append({"epoch": epoch, "step": step, "ce_loss": ce_loss.item(), "sgo_loss": sgo_loss.item(), "alpha": curr_alpha, "total_loss": total_loss.item()})
            epoch_losses.append(total_loss.item())
            pbar.set_description(f"CE: {ce_loss.item():.2f} | α: {curr_alpha:.2f} | Vα: {stats['v_alpha']:.4f}")

            current_loss = float(total_loss.item())
            if current_loss < (best_step_loss - 0.0):
                best_step_loss = current_loss
                model.save_pretrained(best_step_dir)

        # Exit epoch loop on GRG e-stop (after batch loop, before epoch save)
        if GRG_HARD_STOP and grg.should_stop():
            print("[GRG] Hard stop: halting training entirely.")
            break

        if not epoch_losses:
            continue
        epoch_loss = float(np.mean(epoch_losses))
        avg_alpha = float(np.mean(epoch_alphas))

        # Save checkpoints
        model.save_pretrained(CHECKPOINT_DIR / "last")
        if epoch_loss < (best_epoch_loss - 0.0):
            best_epoch_loss = epoch_loss
            stale_epochs = 0
            model.save_pretrained(CHECKPOINT_DIR / "best")
            print(f"Saved best checkpoint (loss={epoch_loss:.4f}, alpha={avg_alpha:.4f}).")
        else:
            stale_epochs += 1
            if stale_epochs >= 2:
                print("Early stopping triggered.")
                break

    # Save results
    df = pd.DataFrame(history)
    Path("artifacts").mkdir(exist_ok=True)
    df.to_csv("artifacts/specforge_sgo_results.csv", index=False)
    output_path = Path(OUTPUT_DIR)
    if best_step_dir.exists():
        if output_path.exists():
            shutil.rmtree(output_path)
        shutil.copytree(best_step_dir, output_path)
        print(f"Exported best step checkpoint (loss={best_step_loss:.4f}) to {OUTPUT_DIR}/")
    else:
        model.save_pretrained(OUTPUT_DIR)
        print("No best checkpoint was produced; exported current model state.")
    tokenizer.save_pretrained(OUTPUT_DIR)
    if grg_stop_events:
        print(f"GRG stop condition was observed {grg_stop_events} time(s); final export uses best checkpoint.")
    print(f"Retraining complete. Adapter saved to {OUTPUT_DIR}/")

if __name__ == "__main__":
    import shutil
    train()