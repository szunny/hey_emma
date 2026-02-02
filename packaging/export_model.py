#!/usr/bin/env python3
"""Export the sentence-transformers model to ONNX format.

Run once to create a local ONNX model in resources/models/:
    python packaging/export_model.py

Requires: sentence-transformers, onnxruntime, optimum
"""

import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "resources" / "models" / MODEL_NAME


def main():
    print(f"Exporting {MODEL_NAME} to ONNX format...")
    print(f"Output directory: {OUTPUT_DIR}")

    model = SentenceTransformer(MODEL_NAME, backend="onnx")

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUTPUT_DIR))

    print(f"Model exported to {OUTPUT_DIR}")

    # Verify the export
    print("Verifying ONNX model loads correctly...")
    test_model = SentenceTransformer(str(OUTPUT_DIR), backend="onnx")
    embeddings = test_model.encode(["Hallo Welt"])
    print(f"Embedding shape: {embeddings.shape}")
    print("Export successful!")


if __name__ == "__main__":
    sys.exit(main() or 0)
