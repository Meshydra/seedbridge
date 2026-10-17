"""Retrieval over the funding knowledge base (app/knowledge/*.md).

Each `## section` of each file is one chunk. Chunks are embedded once with the Token Factory
embedding model and stored in SQLite; at query time the query is embedded and the closest
chunks are passed to the Nemotron models as grounded context, with their titles as citations.
"""
import hashlib
import json
import threading
from pathlib import Path

from .. import db
from . import client

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge"
_lock = threading.Lock()


def _chunks():
    out = []
    for path in sorted(KB_DIR.glob("*.md")):
        doc_title, section, lines = path.stem, None, []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                doc_title = line[2:].strip()
            elif line.startswith("## "):
                if section and lines:
                    out.append((path.stem, f"{doc_title}: {section}", " ".join(lines).strip()))
                section, lines = line[3:].strip(), []
            elif line.strip():
                lines.append(line.strip())
        if section and lines:
            out.append((path.stem, f"{doc_title}: {section}", " ".join(lines).strip()))
    return out


def _fingerprint(chunks) -> str:
    return hashlib.sha1(json.dumps(chunks).encode()).hexdigest()


def ensure_index(on_call=None):
    """Embed the knowledge base if it changed since last time (one batched embedding call)."""
    chunks = _chunks()
    fp = _fingerprint(chunks)
    with _lock:
        stored = db.one("SELECT text FROM kb_chunks WHERE source = '__fingerprint__'")
        if stored and stored["text"] == fp:
            return
        res = client.embed([f"{title}\n{text}" for _, title, text in chunks])
        if on_call:
            on_call(res)
        with db.connect() as c:
            c.execute("DELETE FROM kb_chunks")
            c.executemany("INSERT INTO kb_chunks (source, title, text, embedding_json) VALUES (?,?,?,?)",
                          [(s, t, x, json.dumps(v)) for (s, t, x), v in zip(chunks, res.data)])
            c.execute("INSERT INTO kb_chunks (source, title, text) VALUES ('__fingerprint__', 'fp', ?)", (fp,))


def retrieve(query: str, k=4, on_call=None) -> list[dict]:
    ensure_index(on_call)
    res = client.embed([query])
    if on_call:
        on_call(res)
    qv = res.data[0]
    rows = db.all_("SELECT source, title, text, embedding_json FROM kb_chunks WHERE embedding_json IS NOT NULL")
    for r in rows:
        r["score"] = client.cosine(qv, json.loads(r.pop("embedding_json")))
    return sorted(rows, key=lambda r: -r["score"])[:k]


def as_context(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{c['title']}]\n{c['text']}" for c in chunks)
