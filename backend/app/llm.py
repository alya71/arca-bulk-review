"""Model access. Open-weight models only: Ollama (self-hosted) or Fireworks (hosted, for the demo;
in production the same weights run in the customer's cloud). The pipeline only sees LLMProvider."""
import json
import os
from pathlib import Path
from typing import Protocol

import httpx


def _load_dotenv(path: Path = Path(__file__).resolve().parents[2] / ".env") -> None:
    """Minimal .env loader (repo root); real environment variables win."""
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, val = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), val.strip().strip("'\""))


_load_dotenv()

FIREWORKS_URL = os.environ.get("FIREWORKS_URL", "https://api.fireworks.ai/inference/v1")
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


class FireworksProvider:
    """OpenAI-compatible chat API with JSON-schema constrained output."""

    def __init__(self, model: str):
        self.model = model
        self.key = os.environ["FIREWORKS_API_KEY"]

    def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        r = httpx.post(f"{FIREWORKS_URL}/chat/completions", timeout=600,
                       headers={"Authorization": f"Bearer {self.key}"}, json={
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "answers", "schema": schema}},
            "temperature": 0,
            "max_tokens": 16384,
        })
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])


def embed(texts: list[str], kind: str = "document") -> list[list[float]]:
    """nomic-embed-text expects task prefixes."""
    prefix = "search_document: " if kind == "document" else "search_query: "
    r = httpx.post(f"{OLLAMA_URL}/api/embed", timeout=120,
                   json={"model": EMBED_MODEL, "input": [prefix + t for t in texts]})
    r.raise_for_status()
    return r.json()["embeddings"]


def get_provider(model: str = EXTRACT_MODEL) -> LLMProvider:
    if model.startswith("accounts/"):  # Fireworks model ids look like accounts/fireworks/models/<name>
        return FireworksProvider(model)
    return OllamaProvider(model)
