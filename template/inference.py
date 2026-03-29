"""inference.py — Load cached Qwen-4B assets and expose predict functions.

This module is imported by server.py and test.py. The model is loaded
lazily on first call and cached for subsequent calls.
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODELS_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_CACHE_DIR = os.path.join(MODELS_DIR, "qwen3-4b")
MODEL_READY_PATH = os.path.join(MODELS_DIR, "model.ready")
THINK_END_TOKEN_ID = 151668

_model = None
_tokenizer = None

DEFAULT_GENERATION_OPTIONS = {
    "max_new_tokens": 96,
    "temperature": 0.7,
    "top_p": 0.9,
    "enable_thinking": True,
}


def _runtime_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        return torch.float16
    return torch.float32


def _normalize_chat_message(message: Any) -> Dict[str, str]:
    if not isinstance(message, dict):
        raise ValueError("Each chat message must be an object with 'role' and 'content'.")

    role = message.get("role")
    content = message.get("content")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("Each chat message must include a non-empty string 'role'.")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Each chat message must include a non-empty string 'content'.")

    return {"role": role.strip(), "content": content.strip()}


def _normalize_messages(features: Any) -> List[Dict[str, str]]:
    if not isinstance(features, list) or not features:
        raise ValueError("Features must be a non-empty list of chat messages.")

    if all(isinstance(item, dict) for item in features):
        return [_normalize_chat_message(item) for item in features]

    raise ValueError("Features must be a list of chat messages with 'role' and 'content'.")


def _normalize_generation_options(
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    merged = {**DEFAULT_GENERATION_OPTIONS, **(options or {})}

    try:
        merged["max_new_tokens"] = int(merged["max_new_tokens"])
    except (TypeError, ValueError) as exc:
        raise ValueError("max_new_tokens must be an integer.") from exc
    if merged["max_new_tokens"] < 1:
        raise ValueError("max_new_tokens must be at least 1.")

    try:
        merged["temperature"] = float(merged["temperature"])
    except (TypeError, ValueError) as exc:
        raise ValueError("temperature must be a number.") from exc
    if merged["temperature"] < 0:
        raise ValueError("temperature must be greater than or equal to 0.")

    try:
        merged["top_p"] = float(merged["top_p"])
    except (TypeError, ValueError) as exc:
        raise ValueError("top_p must be a number.") from exc
    if not 0 < merged["top_p"] <= 1:
        raise ValueError("top_p must be greater than 0 and less than or equal to 1.")

    if not isinstance(merged["enable_thinking"], bool):
        raise ValueError("enable_thinking must be a boolean.")

    return merged


def load_model() -> Tuple[Any, Any]:
    """Load and cache tokenizer/model from disk. Raises FileNotFoundError if missing."""
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        if not (os.path.exists(MODEL_READY_PATH) and os.path.isdir(MODEL_CACHE_DIR)):
            raise FileNotFoundError(
                f"Model not found at '{MODEL_CACHE_DIR}'. Run init.py first."
            )

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_CACHE_DIR)
        _model = AutoModelForCausalLM.from_pretrained(
            MODEL_CACHE_DIR,
            torch_dtype=_runtime_dtype(),
            low_cpu_mem_usage=True,
            device_map="auto" if torch.cuda.is_available() else None,
        )

        if not torch.cuda.is_available():
            _model.to("cpu")

    return _tokenizer, _model


def predict(features: Any, options: Optional[Dict[str, Any]] = None) -> str:

    strart_time = time.perf_counter()

    """Run text generation for a single chat payload (message list)."""
    messages = _normalize_messages(features)
    generation_options = _normalize_generation_options(options)
    tokenizer, model = load_model()
    enable_thinking = generation_options["enable_thinking"]

    try:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
    except TypeError:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    model_inputs = tokenizer([text], return_tensors="pt", truncation=True)
    target_device = getattr(model, "device", None)
    if target_device is not None:
        model_inputs = {k: v.to(target_device) for k, v in model_inputs.items()}
    else:
        fallback_device = "cuda" if torch.cuda.is_available() else "cpu"
        model_inputs = {k: v.to(fallback_device) for k, v in model_inputs.items()}

    with torch.no_grad():
        output = model.generate(
            **model_inputs,
            max_new_tokens=generation_options["max_new_tokens"],
            do_sample=True,
            temperature=generation_options["temperature"],
            top_p=generation_options["top_p"],
        )

    output_ids = output[0][len(model_inputs["input_ids"][0]):].tolist()

    try:
        think_end_idx = len(output_ids) - output_ids[::-1].index(THINK_END_TOKEN_ID)
    except ValueError:
        think_end_idx = 0

    content = tokenizer.decode(output_ids[think_end_idx:], skip_special_tokens=True).strip()
    if not content:
        content = tokenizer.decode(output[0], skip_special_tokens=True).strip()

    end_time = time.perf_counter()

    elapsed_time = end_time - strart_time
    print(f"Prediction completed in {elapsed_time:.2f} seconds.")

    additional_info = {
        "elapsed_time": elapsed_time,
        "token_count": len(output_ids),
    }

    content["additional_info"] = additional_info
        
    return content


def predict_batch(samples: list, options: Optional[Dict[str, Any]] = None) -> list:
    """Run text generation for a batch of chat payloads (message lists)."""
    if not isinstance(samples, list) or not samples:
        raise ValueError("Batch features must be a non-empty list.")
    if not all(isinstance(sample, list) and sample for sample in samples):
        raise ValueError("Batch features must be a non-empty list of non-empty chat message lists.")
    return [predict(sample, options=options) for sample in samples]
