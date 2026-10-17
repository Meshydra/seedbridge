"""Settings and the model line-up. Everything can be overridden with env vars (see .env.example)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Minimal .env support so there's no extra dependency: KEY=value lines, real env vars win.
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
DATA_DIR = Path(os.getenv("SEEDBRIDGE_DATA", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "seedbridge.db"

SECRET_KEY = os.getenv("SEEDBRIDGE_SECRET", "dev-only-change-me")

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "").strip()
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")

# Demo mode: no key (or SEEDBRIDGE_DEMO=1) -> every model call is answered locally so the
# whole app is clickable without credits. The UI shows a banner while this is on.
DEMO_MODE = not NEBIUS_API_KEY or os.getenv("SEEDBRIDGE_DEMO") == "1"

# One job per model, picked for cost vs. depth. IDs are from the public Token Factory
# catalog (tokenfactory.nebius.com/api/public/models_info); check yours with
# `python scripts/list_models.py`.
MODELS = {
    "intake": os.getenv("MODEL_INTAKE", "nvidia/Nemotron-3_5-Lightning"),           # fast structuring
    "gaps": os.getenv("MODEL_GAPS", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),        # completeness check
    "vision": os.getenv("MODEL_VISION", "nvidia/Nemotron-3.5-Super-VL"),             # pitch-deck slide reading
    "match": os.getenv("MODEL_MATCH", "nvidia/nemotron-3-super-120b-a12b"),          # rerank sponsor matches
    "review": os.getenv("MODEL_REVIEW", "nvidia/Nemotron-3-Ultra-550b-a55b"),        # investor-readiness review
    "draft": os.getenv("MODEL_DRAFT", "nvidia/Nemotron-3-Ultra-550b-a55b"),          # application drafts
    "embed": os.getenv("MODEL_EMBED", "Qwen/Qwen3-Embedding-8B"),                    # semantic matching
}

# Some models are served from different regions; a per-step base URL can be set with
# e.g. BASE_URL_REVIEW=https://... . Falls back to NEBIUS_BASE_URL.
def base_url_for(step: str) -> str:
    return os.getenv(f"BASE_URL_{step.upper()}", NEBIUS_BASE_URL).rstrip("/")

# USD per 1M tokens (input, output), from the public catalog, used for the cost column.
PRICES = {
    "nvidia/Nemotron-3_5-Lightning": (0.06, 0.24),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
    "nvidia/Nemotron-3.5-Super-VL": (0.3, 0.9),
    "nvidia/nemotron-3-super-120b-a12b": (0.3, 0.9),
    "nvidia/Nemotron-3-Ultra-550b-a55b": (1.0, 3.0),
    "Qwen/Qwen3-Embedding-8B": (0.01, 0.0),
}

STAGES = ["Idea", "Prototype", "MVP", "Early revenue", "Growth"]
SECTORS = ["Agriculture", "Climate & Energy", "Education", "Fintech", "Health", "Manufacturing",
           "Retail & E-commerce", "Software & AI", "Tourism", "Logistics", "Social impact", "Other"]
PROGRAM_KINDS = ["Grant", "Equity investment", "Prize / competition", "Accelerator", "Loan / debt"]

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
