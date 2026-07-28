from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
LORA_MODEL = "moinonin/defiqwen25coder"

tokenizer = AutoTokenizer.from_pretrained(LORA_MODEL)

base = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16,
    device_map="auto",
)

model = PeftModel.from_pretrained(base, LORA_MODEL)
