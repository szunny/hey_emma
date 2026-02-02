from __future__ import annotations

import os
from pathlib import Path

import yaml
import chromadb

from emma.config import get_resource_dir
from emma.embeddings import OnnxEmbedder


# Opposite words for disambiguation (ein/aus, lauter/leiser, etc.)
OPPOSITES = {
    "ein": ["aus"],
    "an": ["aus"],
    "aus": ["ein", "an"],
    "hoch": ["runter", "leiser", "niedrig"],
    "lauter": ["leiser", "runter", "niedrig"],
    "runter": ["hoch", "lauter"],
    "leiser": ["lauter", "hoch"],
    "auf": ["zu", "ab"],
    "zu": ["auf"],
}


def load_commands(yaml_path: str | None = None) -> list[dict]:
    """Load command definitions from YAML file."""
    if yaml_path is None:
        path = get_resource_dir() / "commands.yaml"
    else:
        path = Path(yaml_path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["commands"]


def load_embedding_model(model_name: str | None = None) -> OnnxEmbedder:
    """Load the embedding model.

    Uses the lightweight OnnxEmbedder when a local ONNX model exists.
    Falls back to sentence_transformers for remote model download (dev only).
    """
    if model_name is None:
        model_name = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    # Prefer local ONNX model — uses lightweight OnnxEmbedder (no torch needed)
    model_path = get_resource_dir() / "models" / model_name
    if model_path.exists():
        print(f"Lade Embedding-Modell (lokal ONNX): {model_path}")
        return OnnxEmbedder(model_path)

    # Fallback: use sentence_transformers for remote download (dev mode only).
    # importlib.import_module avoids PyInstaller's static import scanner
    # bundling sentence_transformers (and its torch dependency) into the app.
    print(f"Lade Embedding-Modell (remote): {model_name}")
    import importlib
    st = importlib.import_module("sentence_transformers")
    return st.SentenceTransformer(model_name, backend="onnx")


def setup_chroma_db() -> tuple[chromadb.Client, chromadb.Collection]:
    """Initialize ChromaDB client and collection."""
    client = chromadb.Client()
    # Delete existing collection to start fresh
    try:
        client.delete_collection("commands")
    except Exception:
        pass
    collection = client.create_collection("commands")
    return client, collection


def index_commands(
    collection: chromadb.Collection,
    embed_model: OnnxEmbedder,
    commands: list[dict],
) -> dict[str, dict]:
    """Index all command triggers into ChromaDB. Returns a mapping from trigger text to command dict."""
    trigger_to_command: dict[str, dict] = {}
    all_triggers: list[str] = []
    all_ids: list[str] = []

    for cmd in commands:
        for i, trigger in enumerate(cmd["triggers"]):
            doc_id = f"{cmd['id']}_{i}"
            all_triggers.append(trigger)
            all_ids.append(doc_id)
            trigger_to_command[trigger] = cmd

    embeddings = embed_model.encode(all_triggers).tolist()
    collection.add(documents=all_triggers, embeddings=embeddings, ids=all_ids)
    print(f"{len(all_triggers)} Trigger-Sätze indexiert.")
    return trigger_to_command


def _has_opposite(user_text: str, match_text: str) -> bool:
    """Check if user input and matched command contain opposite keywords."""
    user_lc = user_text.lower()
    match_lc = match_text.lower()
    for word, opps in OPPOSITES.items():
        if word in user_lc:
            for opp in opps:
                if opp in match_lc:
                    return True
    return False


def find_best_command(
    collection: chromadb.Collection,
    embed_model: OnnxEmbedder,
    input_text: str,
    trigger_to_command: dict[str, dict],
    threshold: float = 15.0,
) -> tuple[dict | None, float]:
    """Find the best matching command for the input text.

    Returns (command_dict, distance) or (None, 0.0) if no match found.
    """
    input_emb = embed_model.encode([input_text])[0].tolist()
    results = collection.query(query_embeddings=[input_emb], n_results=5)

    if not results["documents"] or not results["documents"][0]:
        print("DEBUG: Keine Ergebnisse von ChromaDB.")
        return None, 0.0

    # Debug: show raw results
    for i, (doc, dist) in enumerate(zip(results["documents"][0], results["distances"][0])):
        in_map = doc in trigger_to_command
        opposite = _has_opposite(input_text, doc)
        print(f"  [{i}] '{doc}' dist={dist:.4f} in_map={in_map} opposite={opposite}")

    # Check top matches, skipping those with opposite keywords
    for candidate, distance in zip(results["documents"][0], results["distances"][0]):
        if distance > threshold:
            continue
        if not _has_opposite(input_text, candidate):
            cmd = trigger_to_command.get(candidate)
            if cmd:
                print(f"Match: '{candidate}' (Distanz: {distance:.3f}) → {cmd['id']}")
                return cmd, distance

    return None, 0.0
