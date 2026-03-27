"""init.py — Download and cache Qwen3-4B weights for local inference.

Usage:
    python init.py
"""

import argparse
import json
import os
from datetime import datetime, timezone

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODELS_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_CACHE_DIR = os.path.join(MODELS_DIR, "qwen3-8b")
MODEL_READY_PATH = os.path.join(MODELS_DIR, "model.ready")
MODEL_META_PATH = os.path.join(MODELS_DIR, "model.meta.json")
DEFAULT_MODEL_ID = "Qwen/Qwen3-8B"


def _download_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        return torch.float16
    return torch.float32


def cache_model(model_id: str, force: bool = False) -> None:
    """Download and save the tokenizer/model locally for offline startup."""
    os.makedirs(MODELS_DIR, exist_ok=True)

    if os.path.exists(MODEL_READY_PATH) and not force:
        print(f"Model already prepared at '{MODEL_CACHE_DIR}'.")
        return

    if force and os.path.isdir(MODEL_CACHE_DIR):
        print("Force refresh requested, clearing existing model cache...")
        for root, dirs, files in os.walk(MODEL_CACHE_DIR, topdown=False):
            for file_name in files:
                os.remove(os.path.join(root, file_name))
            for dir_name in dirs:
                os.rmdir(os.path.join(root, dir_name))
        os.rmdir(MODEL_CACHE_DIR)

    torch_dtype = _download_dtype()
    print(f"Downloading '{model_id}' with dtype={torch_dtype} ...")

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch_dtype,
        low_cpu_mem_usage=True,
        device_map="auto" if torch.cuda.is_available() else None,
    )

    tokenizer.save_pretrained(MODEL_CACHE_DIR)
    model.save_pretrained(MODEL_CACHE_DIR)

    with open(MODEL_META_PATH, "w", encoding="utf-8") as meta_fp:
        json.dump(
            {
                "model_id": model_id,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "dtype": str(torch_dtype),
            },
            meta_fp,
            indent=2,
        )

    with open(MODEL_READY_PATH, "w", encoding="utf-8") as ready_fp:
        ready_fp.write("ready\n")

    print(f"Model cached successfully at '{MODEL_CACHE_DIR}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare local Qwen3-4B artifacts.")
    parser.add_argument(
        "--model-id",
        default=os.environ.get("QWEN_MODEL_ID", DEFAULT_MODEL_ID),
        help="Hugging Face model ID to cache locally.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download model assets even if already prepared.",
    )
    args = parser.parse_args()

    cache_model(model_id=args.model_id, force=args.force)
