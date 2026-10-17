"""Thin client for Nebius Token Factory (OpenAI-compatible API) with a local demo fallback.

Every call returns a CallResult with model, latency, token counts and cost, so the UI can show
exactly which NVIDIA model did which job and what it cost.
"""
import base64
import hashlib
import json
import math
import mimetypes
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .. import config


@dataclass
class CallResult:
    data: object
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    demo: bool = False
    raw: str = ""
    cost_usd: float = field(init=False)

    def __post_init__(self):
        price_in, price_out = config.PRICES.get(self.model, (0.0, 0.0))
        self.cost_usd = (self.input_tokens * price_in + self.output_tokens * price_out) / 1_000_000


class AIError(RuntimeError):
    pass


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _strip_reasoning(text: str) -> str:
    # Nemotron reasoning modes can prepend a <think> block; we only want the answer.
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def parse_json(text: str):
    text = _strip_reasoning(text)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise AIError("Model did not return JSON")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start:end + 1])


def _post(step: str, path: str, payload: dict) -> dict:
    url = config.base_url_for(step) + path
    headers = {"Authorization": f"Bearer {config.NEBIUS_API_KEY}"}
    last = None
    for attempt in range(3):
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=180)
        except httpx.HTTPError as exc:
            last = str(exc)
        else:
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code not in (429, 500, 502, 503, 504):
                break
        time.sleep(2 * (attempt + 1))
    raise AIError(last or "request failed")


def chat(step: str, system: str, user: str, *, demo, json_out=True, image_path: str | None = None,
         max_tokens=2000, temperature=0.3) -> CallResult:
    """Run one chat completion for a pipeline step. `demo` is a zero-arg function used in demo mode."""
    model = config.MODELS[step]
    prompt_len = _estimate_tokens(system + user)
    if config.DEMO_MODE:
        started = time.perf_counter()
        time.sleep(random.uniform(0.25, 0.9))  # so the progress UI behaves like the real thing
        data = demo()
        out = json.dumps(data) if json_out else str(data)
        return CallResult(data, model, int((time.perf_counter() - started) * 1000),
                          prompt_len, _estimate_tokens(out), demo=True, raw=out)

    content: object = user
    if image_path:
        mime = mimetypes.guess_type(image_path)[0] or "image/png"
        b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        content = [{"type": "text", "text": user},
                   {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]

    started = time.perf_counter()
    body = _post(step, "/chat/completions", {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    })
    latency = int((time.perf_counter() - started) * 1000)
    text = body["choices"][0]["message"].get("content") or ""
    usage = body.get("usage") or {}
    data = parse_json(text) if json_out else _strip_reasoning(text)
    return CallResult(data, model, latency, usage.get("prompt_tokens", prompt_len),
                      usage.get("completion_tokens", _estimate_tokens(text)), raw=text)


def _demo_vector(text: str, dims=256) -> list[float]:
    vec = [0.0] * dims
    for word in re.findall(r"[a-z]{3,}", text.lower()):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        vec[h % dims] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(texts: list[str]) -> CallResult:
    model = config.MODELS["embed"]
    tokens = sum(_estimate_tokens(t) for t in texts)
    if config.DEMO_MODE:
        started = time.perf_counter()
        vectors = [_demo_vector(t) for t in texts]
        return CallResult(vectors, model, int((time.perf_counter() - started) * 1000) + 40, tokens, 0, demo=True)
    started = time.perf_counter()
    body = _post("embed", "/embeddings", {"model": model, "input": texts})
    vectors = [d["embedding"] for d in sorted(body["data"], key=lambda d: d["index"])]
    usage = body.get("usage") or {}
    return CallResult(vectors, model, int((time.perf_counter() - started) * 1000),
                      usage.get("prompt_tokens", tokens), 0)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
