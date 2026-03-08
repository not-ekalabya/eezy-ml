"""inference.py — Load the trained model and expose predict functions.

This module is imported by server.py and test.py. The model is loaded
lazily on first call and cached for subsequent calls.
"""

import os
import numpy as np
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model", "model.joblib")

_model = None


def load_model():
    """Load and cache the model from disk. Raises FileNotFoundError if missing."""
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Model not found at '{MODEL_PATH}'. Run init.py first."
            )
        _model = joblib.load(MODEL_PATH)
    return _model


def predict(features: list) -> str:
    """Run inference on a single MNIST sample.

    Args:
        features: Flat list of 784 pixel values (0-255) for a 28x28 image.

    Returns:
        Predicted digit label as a string ("0"–"9").
    """
    if len(features) != 784:
        raise ValueError(f"Expected 784 features, got {len(features)}.")
    model = load_model()
    X = np.array(features, dtype=float).reshape(1, -1)
    return str(model.predict(X)[0])


def predict_batch(samples: list) -> list:
    """Run inference on a batch of MNIST samples.

    Args:
        samples: List of samples, each a flat list of 784 pixel values.

    Returns:
        List of predicted digit labels as strings.
    """
    if any(len(s) != 784 for s in samples):
        raise ValueError("Each sample must have exactly 784 features.")
    model = load_model()
    X = np.array(samples, dtype=float)
    return [str(p) for p in model.predict(X)]
