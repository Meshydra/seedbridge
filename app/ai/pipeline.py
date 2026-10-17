"""The multi-model pipeline.

Idea submitted
  1. intake  - Nemotron 3.5 Lightning : turn the form into a clean structured profile
  2. gaps    - Nemotron 3 Nano        : what an investor would ask that the founder hasn't answered
  3. vision  - Nemotron 3.5 Super VL  : read the uploaded pitch-deck slide (optional)
  4. review  - Nemotron 3 Ultra       : investor-readiness scorecard
  5. match   - Qwen3 Embedding + rules, then Nemotron 3 Super reranks and explains each match
On demand
  6. draft   - Nemotron 3 Ultra       : application / cover note tailored to one sponsor program
"""
import json
import re
import traceback
from datetime import date

from .. import db
from . import client

# ---------------------------------------------------------------- helpers

def _record(step, result=None, *, idea_id=None, application_id=None, error=None, model=None):
    db.run(
        "INSERT INTO ai_steps (idea_id, application_id, step, model, status, latency_ms, input_tokens,"
        " output_tokens, cost_usd, demo, error, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        idea_id, application_id, step, result.model if result else model, "error" if error else "done",
        result.latency_ms if result else None, result.input_tokens if result else None,
        result.output_tokens if result else None, result.cost_usd if result else None,
        int(bool(result and result.demo)), error, db.now())


def _csv(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def idea_text(idea: dict) -> str:
    fields = [("Title", "title"), ("One-liner", "one_liner"), ("Problem", "problem"),
              ("Solution", "solution"), ("Sector", "sector"), ("Stage", "stage"), ("Country", "country"),
              ("Funding ask (USD)", "ask_usd"), ("Business model", "business_model"), ("Team", "team"),
              ("Traction", "traction"), ("Use of funds", "use_of_funds")]
    return "\n".join(f"{label}: {idea.get(key) or '(not provided)'}" for label, key in fields)


def program_text(p: dict) -> str:
    return (f"{p['name']} ({p['kind']}). {p.get('description') or ''} Criteria: {p.get('criteria') or ''}. "
            f"Sectors: {p.get('sectors') or 'any'}. Stages: {p.get('stages') or 'any'}. "
            f"Countries: {p.get('countries') or 'any'}.")


_STOP = set("""that this with from have will your their they them into than then also only more most
over under about which while where when what would could should there these those being been were
idea ideas stage early sri lanka india bangladesh founders founder program programs grant grants
other made make makes using used each every year years month months plan plans clear""".split())


def _words(text):
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _STOP}


def rule_concerns(idea: dict, p: dict) -> list[str]:
    """Hard eligibility checks we can do without a model."""
    concerns = []
    stages, sectors, countries = _csv(p.get("stages")), _csv(p.get("sectors")), _csv(p.get("countries"))
    if stages and idea.get("stage") not in stages:
        concerns.append(f"Program targets {', '.join(stages)}; idea is at {idea.get('stage') or 'unknown'} stage")
    if sectors and idea.get("sector") not in sectors:
        concerns.append(f"Sector {idea.get('sector') or 'unknown'} is outside {', '.join(sectors)}")
    if countries and not any(c.lower() in ("any", "global") for c in countries) \
            and (idea.get("country") or "").lower() not in [c.lower() for c in countries]:
        concerns.append(f"Open to {', '.join(countries)} only")
    ask = idea.get("ask_usd") or 0
    if ask and p.get("max_usd") and ask > p["max_usd"] * 1.5:
        concerns.append(f"Ask ${ask:,} is well above the ${p['max_usd']:,} maximum")
    if ask and p.get("min_usd") and ask < p["min_usd"] * 0.5:
        concerns.append(f"Ask ${ask:,} is below the ${p['min_usd']:,} minimum")
    if p.get("deadline") and p["deadline"] < date.today().isoformat():
        concerns.append("Deadline has passed")
    return concerns


# ---------------------------------------------------------------- step 1: intake

INTAKE_SYSTEM = """You structure startup and small-business funding applications.
Return ONLY a JSON object with keys:
summary (2 sentences, plain English), customer (who pays), business_model, sector, stage, country,
ask_usd (integer or null), keywords (5-8 lowercase strings), red_flags (list of short strings: claims
that look unrealistic, contradictions, or missing basics; empty list if none)."""


def _demo_intake(idea):
    flags = []
    if not idea.get("traction"):
        flags.append("No traction or validation mentioned")
    if (idea.get("ask_usd") or 0) > 2_000_000 and idea.get("stage") in ("Idea", "Prototype"):
        flags.append("Large ask for a pre-revenue stage")
    words = sorted(_words(f"{idea.get('problem')} {idea.get('solution')} {idea.get('one_liner')}"),
                   key=len, reverse=True)
    return {
        "summary": f"{idea['title']}: {idea.get('one_liner') or idea.get('solution') or ''}".strip()[:300],
        "customer": (idea.get("business_model") or "Not stated")[:120],
        "business_model": idea.get("business_model") or "Not stated",
        "sector": idea.get("sector"), "stage": idea.get("stage"), "country": idea.get("country"),
        "ask_usd": idea.get("ask_usd"),
        "keywords": words[:6],
        "red_flags": flags,
    }


# ---------------------------------------------------------------- step 2: gaps

GAPS_SYSTEM = """You are a funding analyst. Given a founder's application, find what a grant panel or
investor would need that is missing or too vague. Return ONLY JSON:
{"completeness": 0-100, "missing": [{"field": str, "why": str}], "questions": [3-5 sharp follow-up questions]}"""

_KEY_FIELDS = [("problem", "Problem"), ("solution", "Solution"), ("business_model", "Business model"),
               ("team", "Team"), ("traction", "Traction"), ("use_of_funds", "Use of funds"),
               ("ask_usd", "Funding ask")]


def _demo_gaps(idea):
    missing = []
    for key, label in _KEY_FIELDS:
        value = idea.get(key)
        if not value:
            missing.append({"field": label, "why": f"Panels score {label.lower()} directly; it is blank."})
        elif isinstance(value, str) and len(value) < 60:
            missing.append({"field": label, "why": "Too short to judge; add specifics and numbers."})
    questions = [
        "Who exactly is the first paying customer, and how many of them are there in your market?",
        "What have you already tested, and what did the result show?",
        "How will this funding change your numbers in 12 months?",
    ]
    if not idea.get("team"):
        questions.insert(0, "Who is on the team and why are you the people to build this?")
    return {"completeness": max(15, 100 - 14 * len(missing)), "missing": missing, "questions": questions[:5]}


# ---------------------------------------------------------------- step 3: vision

VISION_SYSTEM = """You read pitch-deck slides. Return ONLY JSON:
{"slide_summary": str, "claims": [str], "numbers": [{"label": str, "value": str}],
"consistency": "any mismatch between the slide and the written application, or 'none found'"}"""


def _demo_vision(idea):
    return {"slide_summary": "Demo mode: the slide was stored but not read. With a Nebius key, "
                             "Nemotron 3.5 Super VL extracts its claims and numbers.",
            "claims": [], "numbers": [], "consistency": "not checked in demo mode"}


# ---------------------------------------------------------------- step 4: review

REVIEW_SYSTEM = """You are a seasoned grant-panel chair and early-stage investor. Review the
application honestly; do not flatter. Score each dimension 1-10:
Problem, Solution, Market, Team, Traction, Financial ask.
Return ONLY JSON:
{"overall": 0-100, "verdict": "one sentence", "dimensions": [{"name": str, "score": int, "comment": str}],
"strengths": [3 strings], "risks": [3 strings], "improvements": [3 concrete edits the founder should make],
"best_fit": [funding types that suit this idea now, from: Grant, Equity investment, Prize / competition, Accelerator, Loan / debt]}"""


def _demo_review(idea, gaps):
    def score(key, base=4):
        v = idea.get(key) or ""
        v = str(v)
        return max(1, min(9, base + len(v) // 80 + (1 if re.search(r"\d", v) else 0)))
    dims = [
        {"name": "Problem", "score": score("problem"), "comment": "Clear when it names who suffers and how often."},
        {"name": "Solution", "score": score("solution"), "comment": "Show why this beats what people do today."},
        {"name": "Market", "score": score("one_liner", 3), "comment": "Add a bottom-up market size."},
        {"name": "Team", "score": score("team", 3), "comment": "Relevant experience carries a lot of weight."},
        {"name": "Traction", "score": score("traction", 2), "comment": "Pilots, sign-ups or revenue de-risk the ask."},
        {"name": "Financial ask", "score": score("use_of_funds", 3), "comment": "Tie each dollar to a milestone."},
    ]
    overall = round(sum(d["score"] for d in dims) / len(dims) * 10 * 0.6 + gaps["completeness"] * 0.4)
    stage = idea.get("stage")
    best = ["Grant", "Prize / competition", "Accelerator"] if stage in ("Idea", "Prototype") else \
           ["Equity investment", "Accelerator", "Loan / debt"]
    weakest = sorted(dims, key=lambda d: d["score"])[:3]
    return {
        "overall": overall,
        "verdict": "Promising but needs evidence before an investor meeting." if overall < 70
                   else "Ready to send to well-matched programs.",
        "dimensions": dims,
        "strengths": [f"{d['name']} is the strongest part of the application" for d in
                      sorted(dims, key=lambda d: -d["score"])[:3]],
        "risks": [f"{d['name']} is thin ({d['score']}/10)" for d in weakest],
        "improvements": [f"Strengthen {d['name'].lower()}: {d['comment']}" for d in weakest],
        "best_fit": best,
    }


# ---------------------------------------------------------------- step 5: match

MATCH_SYSTEM = """You match founders to funding programs. For each candidate program decide how well
the idea fits, using the program's criteria and the eligibility concerns already found by rules.
Return ONLY JSON: {"matches": [{"program_id": int, "fit_score": 0-100, "reason": "1-2 sentences, specific",
"concerns": [short strings]}]} sorted by fit_score descending. Penalise hard eligibility failures heavily."""


def _demo_rerank(idea, candidates):
    words = _words(idea_text(idea))
    out = []
    for c in candidates:
        overlap = sorted(words & _words(program_text(c["program"])), key=len, reverse=True)[:3]
        p = c["program"]
        targeted = (15 * (idea.get("sector") in _csv(p.get("sectors")))
                    + 8 * (idea.get("stage") in _csv(p.get("stages")))
                    + 5 * ((idea.get("country") or "").lower() in [x.lower() for x in _csv(p.get("countries"))]))
        fit = round(35 + c["similarity"] * 40 + targeted - 18 * len(c["concerns"]))
        reason = f"Shares focus on {', '.join(overlap)}." if overlap else "General fit on stage and funding size."
        out.append({"program_id": c["program"]["id"], "fit_score": max(5, min(97, fit)),
                    "reason": reason + f" {c['program']['kind']} suits a {idea.get('stage', '').lower()}-stage idea.",
                    "concerns": c["concerns"]})
    return {"matches": sorted(out, key=lambda m: -m["fit_score"])}


def _ensure_program_embeddings(programs, idea_id=None):
    todo = [p for p in programs if not p.get("embedding_json")]
    if not todo:
        return
    res = client.embed([program_text(p) for p in todo])
    _record("embed", res, idea_id=idea_id)
    for p, vec in zip(todo, res.data):
        p["embedding_json"] = json.dumps(vec)
        db.run("UPDATE programs SET embedding_json = ? WHERE id = ?", p["embedding_json"], p["id"])


def _rerank_and_store(idea, profile, review, candidates, idea_id):
    payload = {
        "idea": idea_text(idea), "profile": profile,
        "review_verdict": (review or {}).get("verdict"),
        "candidates": [{"program_id": c["program"]["id"], "program": program_text(c["program"]),
                        "min_usd": c["program"].get("min_usd"), "max_usd": c["program"].get("max_usd"),
                        "deadline": c["program"].get("deadline"), "rule_concerns": c["concerns"],
                        "semantic_similarity": round(c["similarity"], 3)} for c in candidates],
    }
    res = client.chat("match", MATCH_SYSTEM, json.dumps(payload), demo=lambda: _demo_rerank(idea, candidates))
    _record("match", res, idea_id=idea_id)
    sims = {c["program"]["id"]: c["similarity"] for c in candidates}
    for m in res.data.get("matches", []):
        pid = int(m.get("program_id", 0))
        if pid not in sims:
            continue  # ignore anything the model invented
        db.run(
            "INSERT INTO matches (idea_id, program_id, similarity, fit_score, reason, concerns, created_at)"
            " VALUES (?,?,?,?,?,?,?) ON CONFLICT(idea_id, program_id) DO UPDATE SET similarity=excluded.similarity,"
            " fit_score=excluded.fit_score, reason=excluded.reason, concerns=excluded.concerns, created_at=excluded.created_at",
            idea_id, pid, sims[pid], int(m.get("fit_score", 0)), m.get("reason", ""),
            json.dumps(m.get("concerns") or []), db.now())


def match_idea(idea_id: int, top_k=6):
    idea = db.one("SELECT * FROM ideas WHERE id = ?", idea_id)
    programs = db.all_("SELECT * FROM programs")
    if not programs:
        return
    _ensure_program_embeddings(programs, idea_id)
    idea_vec = db.loads(idea["embedding_json"])
    candidates = []
    for p in programs:
        sim = client.cosine(idea_vec, db.loads(p["embedding_json"], []))
        candidates.append({"program": p, "similarity": sim, "concerns": rule_concerns(idea, p)})
    candidates.sort(key=lambda c: (len(c["concerns"]), -c["similarity"]))
    db.run("DELETE FROM matches WHERE idea_id = ?", idea_id)
    _rerank_and_store(idea, db.loads(idea["profile_json"], {}), db.loads(idea["review_json"], {}),
                      candidates[:top_k], idea_id)


# ---------------------------------------------------------------- orchestration

def process_idea(idea_id: int):
    db.run("UPDATE ideas SET status='running', updated_at=? WHERE id=?", db.now(), idea_id)
    db.run("DELETE FROM ai_steps WHERE idea_id=? AND application_id IS NULL", idea_id)
    step = "intake"
    try:
        idea = db.one("SELECT * FROM ideas WHERE id = ?", idea_id)
        text = idea_text(idea)

        res = client.chat("intake", INTAKE_SYSTEM, text, demo=lambda: _demo_intake(idea), max_tokens=800)
        _record("intake", res, idea_id=idea_id)
        profile = res.data
        db.run("UPDATE ideas SET profile_json=? WHERE id=?", json.dumps(profile), idea_id)

        step = "gaps"
        res = client.chat("gaps", GAPS_SYSTEM, text, demo=lambda: _demo_gaps(idea), max_tokens=900)
        _record("gaps", res, idea_id=idea_id)
        gaps = res.data
        db.run("UPDATE ideas SET gaps_json=? WHERE id=?", json.dumps(gaps), idea_id)

        deck = None
        if idea.get("deck_path"):
            step = "vision"
            res = client.chat("vision", VISION_SYSTEM, "Written application:\n" + text,
                              demo=lambda: _demo_vision(idea), image_path=idea["deck_path"], max_tokens=900)
            _record("vision", res, idea_id=idea_id)
            deck = res.data
            db.run("UPDATE ideas SET deck_json=? WHERE id=?", json.dumps(deck), idea_id)

        step = "review"
        review_input = json.dumps({"application": text, "structured_profile": profile,
                                   "gaps": gaps, "pitch_deck": deck})
        res = client.chat("review", REVIEW_SYSTEM, review_input, demo=lambda: _demo_review(idea, gaps),
                          max_tokens=2500)
        _record("review", res, idea_id=idea_id)
        db.run("UPDATE ideas SET review_json=? WHERE id=?", json.dumps(res.data), idea_id)

        step = "embed"
        res = client.embed([f"{profile.get('summary', '')} {' '.join(profile.get('keywords', []))}\n{text}"])
        _record("embed", res, idea_id=idea_id)
        db.run("UPDATE ideas SET embedding_json=? WHERE id=?", json.dumps(res.data[0]), idea_id)

        step = "match"
        match_idea(idea_id)
        db.run("UPDATE ideas SET status='done', updated_at=? WHERE id=?", db.now(), idea_id)
    except Exception as exc:  # keep the app usable and show what broke
        traceback.print_exc()
        _record(step, idea_id=idea_id, error=str(exc)[:500], model=client.config.MODELS.get(step, step))
        db.run("UPDATE ideas SET status='error', updated_at=? WHERE id=?", db.now(), idea_id)


def match_program(program_id: int):
    """A sponsor added a program: score it against every shared, analysed idea."""
    program = db.one("SELECT * FROM programs WHERE id = ?", program_id)
    _ensure_program_embeddings([program])
    vec = db.loads(program["embedding_json"], [])
    ideas = db.all_("SELECT * FROM ideas WHERE status='done' AND share=1 AND embedding_json IS NOT NULL")
    for idea in ideas:
        try:
            candidate = {"program": program, "similarity": client.cosine(db.loads(idea["embedding_json"]), vec),
                         "concerns": rule_concerns(idea, program)}
            _rerank_and_store(idea, db.loads(idea["profile_json"], {}), db.loads(idea["review_json"], {}),
                              [candidate], idea["id"])
        except Exception:
            traceback.print_exc()


# ---------------------------------------------------------------- step 6: draft

DRAFT_SYSTEM = """You write funding applications for founders. Write a cover note / application
summary (350-500 words) addressed to the program below. Use only facts from the application;
where a fact is missing write [ADD: what is needed] instead of inventing it. Plain text, short
headed sections: Summary, Why this program, The problem, Our solution, Traction, The ask and use of funds, Team."""


def _demo_draft(idea, program, review):
    gap = lambda key: idea.get(key) or f"[ADD: {key.replace('_', ' ')}]"
    ask = f"${idea['ask_usd']:,}" if idea.get("ask_usd") else "[ADD: amount]"
    return (
        f"To the {program['name']} team,\n\n"
        f"Summary\n{idea['title']} - {gap('one_liner')}\n\n"
        f"Why this program\nYour {program['kind'].lower()} focuses on {program.get('sectors') or 'founders like us'}; "
        f"we are a {(idea.get('stage') or '').lower()}-stage {idea.get('sector') or ''} venture in {idea.get('country') or '[ADD: country]'}.\n\n"
        f"The problem\n{gap('problem')}\n\n"
        f"Our solution\n{gap('solution')}\n\n"
        f"Traction\n{gap('traction')}\n\n"
        f"The ask and use of funds\nWe are requesting {ask}. {gap('use_of_funds')}\n\n"
        f"Team\n{gap('team')}\n\n"
        f"(Demo-mode draft. With a Nebius key this is written by Nemotron 3 Ultra using the review: "
        f"{(review or {}).get('verdict', '')})"
    )


def draft_application(application_id: int):
    app_row = db.one("SELECT * FROM applications WHERE id = ?", application_id)
    idea = db.one("SELECT * FROM ideas WHERE id = ?", app_row["idea_id"])
    program = db.one("SELECT * FROM programs WHERE id = ?", app_row["program_id"])
    review = db.loads(idea["review_json"], {})
    try:
        payload = json.dumps({"program": program_text(program), "application": idea_text(idea),
                              "review_improvements": review.get("improvements")})
        res = client.chat("draft", DRAFT_SYSTEM, payload, demo=lambda: _demo_draft(idea, program, review),
                          json_out=False, max_tokens=1500, temperature=0.5)
        _record("draft", res, idea_id=idea["id"], application_id=application_id)
        db.run("UPDATE applications SET draft=?, status='draft', updated_at=? WHERE id=?",
               res.data, db.now(), application_id)
    except Exception as exc:
        traceback.print_exc()
        _record("draft", idea_id=idea["id"], application_id=application_id, error=str(exc)[:500],
                model=client.config.MODELS["draft"])
        db.run("UPDATE applications SET status='error', updated_at=? WHERE id=?", db.now(), application_id)
