"""Model access. Everything goes through Ollama (open-weight, self-hosted) by default;
swap OllamaProvider for a Bedrock/Vertex/Anthropic provider without touching the pipeline."""
import json
import os
from typing import Protocol

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "llama3.1:latest")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
NUM_CTX = int(os.environ.get("NUM_CTX", "8192"))


class LLMProvider(Protocol):
    model: str

    def generate_json(self, system: str, prompt: str, schema: dict) -> dict: ...


class OllamaProvider:
    def __init__(self, model: str = EXTRACT_MODEL):
        self.model = model

    def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", timeout=600, json={
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "format": schema,  # constrained decoding to the JSON schema
            "stream": False,
            "options": {"temperature": 0, "num_ctx": NUM_CTX},
        })
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])


def embed(texts: list[str], kind: str = "document") -> list[list[float]]:
    """nomic-embed-text expects task prefixes."""
    prefix = "search_document: " if kind == "document" else "search_query: "
    r = httpx.post(f"{OLLAMA_URL}/api/embed", timeout=120,
                   json={"model": EMBED_MODEL, "input": [prefix + t for t in texts]})
    r.raise_for_status()
    return r.json()["embeddings"]


def get_provider(model: str = EXTRACT_MODEL) -> LLMProvider:
    return OllamaProvider(model)
