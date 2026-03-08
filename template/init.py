"""init.py — Download MNIST, train a scikit-learn model, and save it.

Usage:
    python init.py
"""

import os
import joblib
from sklearn.datasets import fetch_openml
from sklearn.linear_model import SGDClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_PATH = os.path.join(MODELS_DIR, "model.joblib")


def download_data():
    """Download the MNIST dataset into the data directory."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Downloading MNIST dataset...")
    mnist = fetch_openml("mnist_784", version=1, as_frame=False, data_home=DATA_DIR)
    X, y = mnist.data, mnist.target
    print(f"Downloaded {X.shape[0]} samples with {X.shape[1]} features each.")
    return X, y


def train(X, y):
    """Train an SGD classifier pipeline on the given data and return it."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", SGDClassifier(random_state=42, max_iter=10, n_jobs=-1)),
    ])

    print("Training model...")
    pipeline.fit(X_train, y_train)

    score = pipeline.score(X_test, y_test)
    print(f"Test accuracy: {score:.4f}")
    return pipeline


def save_model(model):
    """Persist the trained model to the models directory."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")


if __name__ == "__main__":
    X, y = download_data()
    model = train(X, y)
    save_model(model)
