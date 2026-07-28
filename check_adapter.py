import torch
import os
from safetensors.torch import load_file

adapter_path = os.path.expanduser("~/.cache/huggingface/hub/models--moinonin--defiqwen25coder")
snapshots = os.path.join(adapter_path, "snapshots")
hash_dir = os.listdir(snapshots)[0]   # ensure this is the snapshot actually used
adapter_file = os.path.join(snapshots, hash_dir, "adapter_model.safetensors")

state_dict = load_file(adapter_file)

# Print all keys that contain "embed_tokens"
print("Keys with 'embed_tokens':")
for k in state_dict.keys():
    if "embed_tokens" in k:
        print(k)

# Also check if any key has four "model" segments
print("\nAny key with 'model.model.model.model':")
for k in state_dict.keys():
    if "model.model.model.model" in k:
        print(k)