"""Check that every model SeedBridge is configured to use is available to your Nebius key.

    python scripts/list_models.py
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

if not config.NEBIUS_API_KEY:
    sys.exit("Set NEBIUS_API_KEY in .env first.")

available = set()
for base in {config.base_url_for(step) for step in config.MODELS}:
    r = httpx.get(base + "/models", headers={"Authorization": f"Bearer {config.NEBIUS_API_KEY}"}, timeout=30)
    r.raise_for_status()
    available |= {m["id"] for m in r.json().get("data", [])}

print(f"{len(available)} models visible to this key. NVIDIA ones:")
for model_id in sorted(m for m in available if m.lower().startswith("nvidia/")):
    print("  ", model_id)
print("\nConfigured steps:")
for step, model_id in config.MODELS.items():
    print(f"  {'OK     ' if model_id in available else 'MISSING'} {step:7} {model_id}")
