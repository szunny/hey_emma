"""Lightweight ONNX-based sentence embedder.

Replaces sentence_transformers at runtime to avoid the torch dependency.
Uses onnxruntime for inference and tokenizers (HuggingFace Rust library)
for text tokenization.

The exported model directory must contain:
  - onnx/model.onnx       (the ONNX transformer model)
  - tokenizer.json         (HuggingFace fast tokenizer)
  - 1_Pooling/config.json  (pooling configuration)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class OnnxEmbedder:
    """Sentence embedder using ONNX runtime + tokenizers directly."""

    def __init__(self, model_dir: str | Path) -> None:
        model_dir = Path(model_dir)

        # Load tokenizer
        tokenizer_path = model_dir / "tokenizer.json"
        if not tokenizer_path.exists():
            raise FileNotFoundError(f"tokenizer.json not found in {model_dir}")
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))

        # Read max length from tokenizer_config.json
        tok_config_path = model_dir / "tokenizer_config.json"
        self.max_length = 128
        if tok_config_path.exists():
            with open(tok_config_path) as f:
                tok_config = json.load(f)
            self.max_length = tok_config.get("model_max_length", 128)

        # Configure tokenizer truncation and padding
        self.tokenizer.enable_truncation(max_length=self.max_length)
        self.tokenizer.enable_padding(length=None, pad_id=1, pad_token="<pad>")

        # Load ONNX model
        onnx_path = model_dir / "onnx" / "model.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"model.onnx not found in {model_dir / 'onnx'}")

        self.session = ort.InferenceSession(
            str(onnx_path),
            providers=["CPUExecutionProvider"],
        )
        self.input_names = [inp.name for inp in self.session.get_inputs()]

        # Read pooling config
        pooling_config_path = model_dir / "1_Pooling" / "config.json"
        self.pooling_mode = "mean"
        if pooling_config_path.exists():
            with open(pooling_config_path) as f:
                pooling = json.load(f)
            if pooling.get("pooling_mode_cls_token"):
                self.pooling_mode = "cls"
            elif pooling.get("pooling_mode_max_tokens"):
                self.pooling_mode = "max"

    def encode(self, sentences: list[str]) -> np.ndarray:
        """Encode sentences into normalized embeddings.

        Args:
            sentences: List of text strings to encode.

        Returns:
            numpy array of shape (len(sentences), embedding_dim).
        """
        encoded = self.tokenizer.encode_batch(sentences)

        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

        feeds = {}
        if "input_ids" in self.input_names:
            feeds["input_ids"] = input_ids
        if "attention_mask" in self.input_names:
            feeds["attention_mask"] = attention_mask
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = token_type_ids

        outputs = self.session.run(None, feeds)
        token_embeddings = outputs[0]  # (batch, seq_len, hidden_dim)

        # Pool
        if self.pooling_mode == "cls":
            embeddings = token_embeddings[:, 0, :]
        elif self.pooling_mode == "max":
            mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
            token_embeddings[mask_expanded == 0] = -1e9
            embeddings = token_embeddings.max(axis=1)
        else:  # mean pooling
            mask_expanded = attention_mask[:, :, np.newaxis].astype(np.float32)
            sum_embeddings = (token_embeddings * mask_expanded).sum(axis=1)
            sum_mask = mask_expanded.sum(axis=1).clip(min=1e-9)
            embeddings = sum_embeddings / sum_mask

        # L2 normalize
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True).clip(min=1e-9)
        embeddings = embeddings / norms

        return embeddings
