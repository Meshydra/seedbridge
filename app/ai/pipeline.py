"""The multi-model pipeline.

Idea submitted
  1. intake   - Nemotron 3.5 Lightning : structured profile + web search queries
  2. research - Tavily web search, summarised by Nemotron 3.5 Lightning (market snapshot with sources)
  3. gaps     - Nemotron 3 Nano        : what a panel will ask, grounded in retrieved stage benchmarks (RAG)
  4. vision   - Nemotron 3.5 Super VL  : read the uploaded pitch-deck slide (optional)
  5. review   - Nemotron 3 Ultra       : investor-readiness scorecard, grounded in the knowledge base (RAG)
                                         and the market research, with citations
  6. match    - Qwen3 Embedding + rules, then Nemotron 3 Super reranks and explains each match
On demand
  7. draft    - Nemotron 3 Ultra       : application tailored to one program, grounded in writing guidance (RAG)

RAG = app/ai/rag.py: app/knowledge/*.md chunked by section, embedded with Qwen3-Embedding-8B.
"""
import json
import re
import traceback
from datetime import date

from .. import db
from . import client, rag, research

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
              ("Solution", "solution"), ("Sector", "sector"), ("Funding stage", "stage"),
              ("Product status", "product_status"), ("Country", "country"),
              ("Funding ask (USD)", "ask_usd"), ("Business model", "business_model"), ("Team", "team"),
              ("Traction", "traction"), ("Use of funds", "use_of_funds")]
    return "\n".join(f"{label}: {idea.get(key) or '(not provided)'}" for label, key in fields)


def program_text(p: dict) -> str:
    return (f"{p['name']} ({p['kind']}). {p.get('description') or ''} Criteria: {p.get('criteria') or ''}. "
            f"Sectors: {p.get('sectors') or 'any'}. Stages: {p.get('stages') or 'any'}. "
            f"Countries: {p.get('countries') or 'any'}.")


_STOP = set("""that this with from have will your their they them into than then also only more most
over under about which while where when what would could should there these those being been were
idea ideas stage early just live business series seed sri lanka india bangladesh founders founder program programs grant grants
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
that look unrealistic, contradictions, or missing basics; empty list if none),
search_queries (2-3 web search queries that would find the market size, competitors and recent
news for this idea in its country)."""


def _demo_intake(idea):
    flags = []
    if not idea.get("traction"):
        flags.append("No traction or validation mentioned")
    if (idea.get("ask_usd") or 0) > 2_000_000 and idea.get("stage") in ("Just an idea", "Pre-seed"):
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
        "search_queries": [f"{idea['title']} competitors {idea.get('country') or ''}".strip(),
                           f"{idea.get('sector')} market size {idea.get('country') or ''}".strip()],
    }


# ---------------------------------------------------------------- step 2: research

RESEARCH_SYSTEM = """You are a market analyst. Using ONLY the web search results provided, write a short
market snapshot for the idea. Return ONLY JSON:
{"snapshot": "3-4 sentences", "market_size": "figure with source title, or 'not found'",
"competitors": [{"name": str, "note": "what they do, 1 sentence", "url": str}],
"signals": ["recent news or trends that matter, with source title"],
"sources": [{"title": str, "url": str}]}
Never invent a URL or a number that is not in the results."""


# ---------------------------------------------------------------- step 3: gaps

GAPS_SYSTEM = """You are a funding analyst. Given a founder's application and reference guidance on
what funders expect at this stage, find what a grant panel or investor would need that is missing
or too vague. Return ONLY JSON:
{"completeness": 0-100, "missing": [{"field": str, "why": str}], "questions": [3-5 sharp follow-up questions]}"""

_KEY_FIELDS = [("problem", "Problem"), ("solution", "Solution"), ("business_model", "Business model"),
               ("team", "Team"), ("traction", "Traction"), ("use_of_funds", "Use of funds"),
               ("ask_usd", "Funding ask")]


# Preview-mode wording: what an experienced reviewer would say, picked by how strong each answer is.
_GAP_WHY = {
    "Problem": "Panels score the problem first. Say who has it, how often, and what it costs them.",
    "Solution": "Explain how it works in practice and why it beats what people do today.",
    "Business model": "Say who pays, how much and how often. Funders need to see a path to income.",
    "Team": "Name the people and the experience that makes you credible for this.",
    "Traction": "Any evidence counts at this stage: interviews, a pilot, sign-ups or first sales.",
    "Use of funds": "Split the money into two or three buckets, each tied to a milestone.",
    "Funding ask": "State the exact amount; programs filter on ticket size.",
}
_STAGE_QUESTIONS = {
    "Just an idea": ["How many potential customers have you spoken to, and what did they say?",
                     "What is the cheapest test that would prove people want this?"],
    "Pre-seed": ["Who are your first five customers, and have any of them paid?",
                 "What will the prototype prove in the next six months?"],
    "Seed": ["What is your month-on-month growth, and what drives it?",
             "What does it cost to win a customer, and how long do they stay?"],
    "Series A+": ["Which channel will scale, and what are its unit economics today?",
                  "Who joins the management team with this round?"],
    "Live business": ["What were revenue and margin over the last 12 months?",
                      "Which growth project does this money fund, and how is it repaid?"],
}


def _demo_gaps(idea):
    missing = []
    for key, label in _KEY_FIELDS:
        value = idea.get(key)
        if not value or (isinstance(value, str) and len(value) < 60):
            missing.append({"field": label, "why": _GAP_WHY[label]})
    questions = list(_STAGE_QUESTIONS.get(idea.get("stage"), _STAGE_QUESTIONS["Pre-seed"]))
    questions.append("How will this funding change your numbers in 12 months?")
    if not idea.get("team"):
        questions.insert(0, "Who is on the team, and why are you the right people to build this?")
    return {"completeness": max(15, 100 - 14 * len(missing)), "missing": missing, "questions": questions[:4]}


# ---------------------------------------------------------------- step 3: vision

VISION_SYSTEM = """You read pitch-deck slides. Return ONLY JSON:
{"slide_summary": str, "claims": [str], "numbers": [{"label": str, "value": str}],
"consistency": "any mismatch between the slide and the written application, or 'none found'"}"""


def _demo_vision(idea):
    return {"slide_summary": "Your slide is saved and will be read alongside your answers in the next full review.",
            "claims": [], "numbers": [], "consistency": "not checked yet"}


# ---------------------------------------------------------------- step 4: review

REVIEW_SYSTEM = """You are a seasoned grant-panel chair and early-stage investor. Review the
application honestly; do not flatter. Judge it against the reference guidance provided (benchmarks
for its funding stage) and the market research, not against later-stage companies.
Score each dimension 1-10:
Problem, Solution, Market, Team, Traction, Financial ask.
Return ONLY JSON:
{"overall": 0-100, "verdict": "one sentence", "dimensions": [{"name": str, "score": int, "comment": str}],
"strengths": [3 strings], "risks": [3 strings], "improvements": [3 concrete edits the founder should make],
"best_fit": [funding types that suit this idea now, from: Grant, Equity investment, Prize / competition, Accelerator, Loan / debt],
"based_on": [titles of the reference guidance sections you relied on]}"""


_DIM_NOTES = {
    # name: (weak comment, solid comment, strength line, risk line, fix line)
    "Problem": ("Needs a sharper picture of who is affected and how often.",
                "Clear, specific and grounded in a real group of people.",
                "The problem is concrete and easy for a panel to picture.",
                "The problem isn't yet tied to a specific group or a cost.",
                "Open with one sentence naming who has the problem, how often, and what it costs them."),
    "Solution": ("Explain how it works day to day and why it beats current options.",
                 "Practical and well matched to the problem.",
                 "The solution fits the problem and looks practical to deliver.",
                 "It's not yet clear why this beats what people do today.",
                 "Add a short before-and-after comparison for one customer."),
    "Market": ("No sense yet of how many customers there are or what they'd pay.",
               "A credible view of who pays and how.",
               "There is a clear paying customer in a reachable market.",
               "Market size is missing, so the upside is hard to judge.",
               "Add a bottom-up market size: reachable customers x price x frequency."),
    "Team": ("Say who is building this and why they are credible.",
             "Relevant experience for this problem.",
             "The team has directly relevant experience.",
             "The team is thin or not described, which weighs heavily at this stage.",
             "Name each founder's role and one fact that shows they can deliver."),
    "Traction": ("No evidence of demand yet.",
                 "Real evidence of demand, with numbers.",
                 "There is measurable traction, which lowers the risk of the ask.",
                 "Little evidence yet that customers want this.",
                 "Run a small paid pilot or collect letters of intent before applying widely."),
    "Financial ask": ("The ask isn't tied to milestones.",
                      "Sized sensibly and tied to what it buys.",
                      "The ask is sensibly sized for the stage.",
                      "It's unclear what the money achieves.",
                      "Break the ask into two or three milestones, each with a cost and a date."),
}


def _demo_review(idea, gaps, refs=()):
    def score(key, base=4):
        v = str(idea.get(key) or "")
        if not v:
            return 2
        return max(2, min(9, base + len(v) // 50 + (1 if re.search(r"\d", v) else 0)))
    raw = [("Problem", score("problem")), ("Solution", score("solution")), ("Market", score("business_model", 3)),
           ("Team", score("team")), ("Traction", score("traction", 3)), ("Financial ask", score("use_of_funds", 3))]
    dims = [{"name": n, "score": sc, "comment": _DIM_NOTES[n][1 if sc >= 6 else 0]} for n, sc in raw]
    overall = round(sum(d["score"] for d in dims) / len(dims) * 10 * 0.6 + gaps["completeness"] * 0.4)
    stage = idea.get("stage")
    best = {"Just an idea": ["Grant", "Prize / competition"],
            "Pre-seed": ["Grant", "Accelerator", "Prize / competition"],
            "Seed": ["Equity investment", "Accelerator"],
            "Series A+": ["Equity investment"],
            "Live business": ["Loan / debt", "Grant", "Equity investment"]}.get(stage, ["Grant", "Accelerator"])
    ranked = sorted(dims, key=lambda d: -d["score"])
    weakest = ranked[::-1][:3]
    if overall >= 75:
        verdict = "Strong application, ready for well-matched programs."
    elif overall >= 55:
        verdict = "Promising. Close a few gaps before you apply."
    else:
        verdict = "Early, with potential. Build evidence before approaching funders."
    return {
        "overall": overall,
        "verdict": verdict,
        "dimensions": dims,
        "strengths": [_DIM_NOTES[d["name"]][2] for d in ranked[:3] if d["score"] >= 5] or
                     ["The idea is described clearly enough to review."],
        "risks": ([_DIM_NOTES[d["name"]][3] for d in weakest if d["score"] <= 5] + [
            "Competition isn't addressed: say why a larger player can't copy this quickly.",
            ("Retention and churn aren't shown yet; investors at this stage will ask."
             if dict(raw)["Traction"] >= 6 else
             "Key assumptions (price, uptake) haven't been tested with paying customers yet."),
            "Execution risk: the plan depends on a small team delivering several things at once."])[:3],
        "improvements": [_DIM_NOTES[d["name"]][4] for d in weakest],
        "best_fit": best,
        "based_on": [r["title"] for r in refs][:3],
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
        reason = reason if c["concerns"] else reason + " Meets every eligibility rule."
        out.append({"program_id": c["program"]["id"], "fit_score": max(5, min(97, fit)),
                    "reason": reason,
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

        res = client.chat("intake", INTAKE_SYSTEM, text, demo=lambda: _demo_intake(idea), max_tokens=900)
        _record("intake", res, idea_id=idea_id)
        profile = res.data
        db.run("UPDATE ideas SET profile_json=? WHERE id=?", json.dumps(profile), idea_id)

        market = None
        db.run("UPDATE ideas SET research_json=NULL WHERE id=?", idea_id)
        if research.enabled() and profile.get("search_queries"):
            step = "research"
            found = research.search(profile["search_queries"])
            db.run("INSERT INTO ai_steps (idea_id, step, model, status, latency_ms, created_at)"
                   " VALUES (?,?,?,?,?,?)", idea_id, "research", "tavily/search", "done", found["latency_ms"], db.now())
            if found["results"]:
                res = client.chat("intake", RESEARCH_SYSTEM,
                                  json.dumps({"idea": text, "search_results": found["results"]}),
                                  demo=lambda: {}, max_tokens=1200)
                _record("summarise", res, idea_id=idea_id)
                market = res.data
                db.run("UPDATE ideas SET research_json=? WHERE id=?", json.dumps(market), idea_id)

        step = "retrieve"
        refs = rag.retrieve(f"{idea.get('stage')} stage funding expectations {idea.get('sector')} "
                            f"{profile.get('summary', '')}", k=4,
                            on_call=lambda r: _record("retrieve", r, idea_id=idea_id))

        step = "gaps"
        gaps_input = f"{text}\n\nReference guidance:\n{rag.as_context(refs[:3])}"
        res = client.chat("gaps", GAPS_SYSTEM, gaps_input, demo=lambda: _demo_gaps(idea), max_tokens=900)
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
                                   "gaps": gaps, "pitch_deck": deck, "market_research": market,
                                   "reference_guidance": [{"title": r["title"], "text": r["text"]} for r in refs]})
        res = client.chat("review", REVIEW_SYSTEM, review_input, demo=lambda: _demo_review(idea, gaps, refs),
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
        f"Team\n{gap('team')}\n"
    )


def draft_application(application_id: int):
    app_row = db.one("SELECT * FROM applications WHERE id = ?", application_id)
    idea = db.one("SELECT * FROM ideas WHERE id = ?", app_row["idea_id"])
    program = db.one("SELECT * FROM programs WHERE id = ?", app_row["program_id"])
    review = db.loads(idea["review_json"], {})
    try:
        refs = rag.retrieve(f"writing a {program['kind']} application {program.get('criteria') or ''}", k=3,
                            on_call=lambda r: _record("retrieve", r, idea_id=idea["id"], application_id=application_id))
        payload = json.dumps({"program": program_text(program), "application": idea_text(idea),
                              "review_improvements": review.get("improvements"),
                              "market_research": db.loads(idea.get("research_json")),
                              "writing_guidance": rag.as_context(refs)})
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
