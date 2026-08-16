#!/usr/bin/env python3
"""LLM Skill - Unified interface for code generation models"""

import torch
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model, TaskType

from .config import GRGAgentConfig
from .state import Candidate, Strategy


@dataclass
class GenerationResult:
    """Result from a single generation"""
    text: str
    logprobs: List[float]
    tokens: List[int]


class LLMSkill:
    """
    Unified interface for code generation models.
    Supports PyTorch (with LoRA/4-bit) and provides clean generate() interface.
    """
    
    def __init__(self, config: 'GRGAgentConfig'):
        self.config = config
        self.device = config.device
        self.tokenizer = None
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load model with LoRA/4-bit support"""
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        print(f"Loading {self.config.model_id} on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_id)
        
        load_kwargs = {"torch_dtype": torch.bfloat16}
        
        # 4-bit quantization (CUDA only)
        if self.config.load_in_4bit and self.device == "cuda":
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            load_kwargs["device_map"] = "auto"
        else:
            load_kwargs["device_map"] = "auto" if self.device == "cuda" else None
        
        base_model = AutoModelForCausalLM.from_pretrained(
            self.config.model_id,
            **load_kwargs
        )
        
        # Apply LoRA if requested
        if self.config.use_lora:
            from peft import LoraConfig, get_peft_model, TaskType
            
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=self.config.lora_target_modules,
            )
            base_model = get_peft_model(base_model, lora_config)
            print(f"Applied LoRA (r={self.config.lora_r}, alpha={self.config.lora_alpha})")
            base_model.print_trainable_parameters()
        
        if self.device != "cuda" and not self.config.load_in_4bit:
            base_model = base_model.to(self.device)
        
        base_model.eval()
        self.model = base_model
    
    def generate(
        self,
        prompt: str,
        temperature: float = None,
        top_p: float = None,
        max_tokens: int = None,
        top_k: int = None,
        stop_tokens: List[str] = None,
        return_logprobs: bool = True,
        seed: int = None,
    ) -> Candidate:
        """
        Generate a single completion for the given prompt.
        
        Returns:
            Candidate with text, logprobs, and metadata
        """
        if temperature is None:
            temperature = self.config.temperature
        if top_p is None:
            top_p = self.config.top_p
        if max_tokens is None:
            max_tokens = self.config.max_tokens
        
        if seed is not None:
            torch.manual_seed(seed)
        
        # Add stop tokens to stop at function end
        if stop_tokens is None:
            stop_tokens = ["\n\n\n", "\n```", "\n# Example", "```\n"]
        
        # Encode prompt
        input_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
        generated = input_ids.clone()
        
        logprobs_list = []
        tokens_generated = []
        
        with torch.no_grad():
            for _ in range(max_tokens):
                outputs = self.model(generated)
                logits = outputs.logits[:, -1, :] / temperature
                
                # Top-p sampling
                probs = torch.softmax(logits, dim=-1)
                sorted_probs, sorted_indices = torch.sort(probs, descending=True)
                cumulative_probs = torch.cumsum(sorted_probs, dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
                sorted_indices_to_remove[:, 0] = 0
                indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                probs[indices_to_remove] = 0
                probs = probs / probs.sum(dim=-1, keepdim=True)
                
                next_token = torch.multinomial(probs, num_samples=1)
                
                # Logprob of chosen token
                logprobs = torch.log_softmax(logits, dim=-1)
                token_logprob = logprobs.gather(-1, next_token).squeeze(-1)
                logprobs_list.append(token_logprob.item())
                tokens_generated.append(next_token.item())
                
                generated = torch.cat([generated, next_token], dim=-1)
                
                # Check stop tokens
                if next_token.item() == self.tokenizer.eos_token_id:
                    break
                
                # Check custom stop tokens
                if stop_tokens:
                    decoded = self.tokenizer.decode(next_token.item())
                    if any(stop in decoded for stop in stop_tokens):
                        break
        
        # Decode generated text (excluding prompt)
        prompt_len = input_ids.shape[1]
        generated_text = self.tokenizer.decode(
            generated[0, prompt_len:], 
            skip_special_tokens=True
        )
        
        return Candidate(
            text=generated_text,
            logprobs=logprobs_list,
            strategy="default",
            iteration=0,
            metadata={
                "tokens": tokens_generated,
                "temperature": temperature,
                "top_p": top_p,
            }
        )
    
    def generate_batch(
        self,
        prompts: List[str],
        num_candidates: int = 1,
        **kwargs
    ) -> List[List[Candidate]]:
        """Generate multiple candidates for each prompt"""
        results = []
        for prompt in prompts:
            candidates = []
            for _ in range(num_candidates):
                cand = self.generate(prompt, **kwargs)
                candidates.append(cand)
            results.append(candidates)
        return results
    
    def get_logprobs(self, prompt: str, completion: str) -> List[float]:
        """Get logprobs for a given prompt+completion (for scoring)"""
        full_text = prompt + completion
        input_ids = self.tokenizer.encode(full_text, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model(input_ids)
            logits = outputs.logits
            logprobs = torch.log_softmax(logits, dim=-1)
            
            # Get logprobs for completion tokens only
            prompt_len = len(self.tokenizer.encode(prompt, add_special_tokens=False))
            completion_ids = input_ids[0, prompt_len:]
            logprobs_list = []
            
            for i, token_id in enumerate(completion_ids):
                lp = logprobs[0, prompt_len + i - 1, token_id].item()
                logprobs_list.append(lp)
            
            return logprobs_list
    
    def get_embeddings(self, texts: List[str]) -> torch.Tensor:
        """Get embeddings for diversity calculation"""
        # Use last hidden state mean pooling
        inputs = self.tokenizer(texts, padding=True, truncation=True, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)
            hidden = outputs.hidden_states[-1]  # Last layer
            # Mean pooling
            attention_mask = inputs['attention_mask']
            embeddings = (hidden * attention_mask.unsqueeze(-1)).sum(1) / attention_mask.sum(1, keepdim=True)
        
        return embeddings


def create_llm_skill(config: 'GRGAgentConfig') -> 'LLMSkill':
    """Factory function to create LLM skill"""
    return LLMSkill(config)