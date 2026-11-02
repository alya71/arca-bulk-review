"""Model access. Runs on Fireworks AI only: answer extraction (Kimi K3) and search embeddings
(nomic-embed-text v1.5). Both are open-weight, so in production the same weights can run on the
customer's own GPUs behind this same interface. The pipeline only sees LLMProvider and embed()."""
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
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "accounts/fireworks/models/kimi-k3")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5")
EMBED_BATCH = 64


def _headers() -> dict:
    key = os.environ.get("FIREWORKS_API_KEY")
    if not key:
        raise RuntimeError("FIREWORKS_API_KEY is not set. Add it to arca/.env (this app runs on Fireworks only).")
    return {"Authorization": f"Bearer {key}"}


class LLMProvider(Protocol):
    model: str

    def generate_json(self, system: str, prompt: str, schema: dict) -> dict: ...


class FireworksProvider:
    """OpenAI-compatible chat API with JSON-schema constrained output."""

    def __init__(self, model: str = EXTRACT_MODEL):
        self.model = model

    def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        r = httpx.post(f"{FIREWORKS_URL}/chat/completions", timeout=600, headers=_headers(), json={
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
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        r = httpx.post(f"{FIREWORKS_URL}/embeddings", timeout=120, headers=_headers(),
                       json={"model": EMBED_MODEL, "input": [prefix + t for t in texts[i:i + EMBED_BATCH]]})
        r.raise_for_status()
        out += [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
    return out


def where_it_runs(model: str = EXTRACT_MODEL) -> dict:
    """For the Security page: who receives document text for this model."""
    return {"host": "Fireworks AI (hosted inference)", "external": True}


def get_provider(model: str = EXTRACT_MODEL) -> LLMProvider:
    if not model.startswith("accounts/"):  # Fireworks model ids look like accounts/fireworks/models/<name>
        raise ValueError(f"{model!r} is not a Fireworks model id; this app runs on Fireworks only")
    return FireworksProvider(model)
