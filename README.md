<p align="center"><img src="app/static/brand/mark.svg" width="88" alt="SeedBridge logo"></p>

# SeedBridge

**Founders describe a business idea once. SeedBridge reviews it the way a funding panel would, shows exactly what to fix, and matches it to the grants, investors, prizes and accelerators it actually fits. Funders publish programs and get a ranked, pre-reviewed shortlist.**

Built for the **Nebius x NVIDIA Global AI Hackathon**, Best Apps and Agents track. Every AI step runs on **NVIDIA Nemotron open models served by Nebius Token Factory**. The app is designed to run on **Nebius Serverless Endpoints**, with background matching as a **Nebius Serverless Job**.

Licence: [MIT](LICENSE).

## The problem

Early founders, especially outside the big startup hubs, don't know which funding they're eligible for, and they write applications blind. Most rejections are avoidable: wrong funder, wrong stage, a missing number, a budget that doesn't add up. Funders face the mirror image: piles of unsuitable applications screened by hand.

## What it does

**Founders**
- A five-step guided form covers the basics and **where the business is now** (just an idea, pre-seed, seed, Series A+ or a live business), plus whether the product is live. Then problem and solution, team and traction, and the ask, with an optional pitch slide.
- A **readiness score** out of 100 across six dimensions, judged against what funders expect *at that stage*, with strengths, risks and the three fixes that matter most.
- **"What a panel will ask"** lists the missing information and the questions to prepare for.
- A **market snapshot** from live web research: competitors, market size and sources.
- **Matched funders**, ranked by fit, with eligibility problems flagged before you waste time applying.
- **One-click applications** tailored to each funder and written only from your own facts. Missing ones are marked `[ADD: …]`.
- A profile photo and full control over whether funders can see your idea.

**Funders**
- List a grant, equity fund, prize, accelerator or loan, with stages, sectors, countries and ticket size.
- See the founders who fit, best first, each with a reason and the full review.
- Applications arrive pre-reviewed. Shortlist, decline or request an intro; requesting an intro shares contact details with both sides.

## How it uses NVIDIA Nemotron on Nebius Token Factory

Seven AI steps, each on the smallest model that does the job well. Only the deep judgement goes to Ultra.

| # | Step | Model (Token Factory ID) | Why this model |
|---|---|---|---|
| 1 | Structure the application and write web-search queries | `nvidia/Nemotron-3_5-Lightning` | Runs on every submission: fast and cheap |
| 2 | Market research: Tavily search, then summarised with sources | Tavily + `nvidia/Nemotron-3_5-Lightning` | Grounds the review in live evidence; never invents sources |
| 3 | What a panel will ask (RAG-grounded) | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Checklist-style gap analysis |
| 4 | Read the pitch slide | `nvidia/Nemotron-3.5-Super-VL` | Vision: pulls out claims and numbers and checks them against the written answers |
| 5 | Readiness review (RAG-grounded, cited) | `nvidia/Nemotron-3-Ultra-550b-a55b` | The deepest judgement in the product |
| 6 | Match funders: embeddings and hard rules shortlist, then a model reranks and explains | `Qwen/Qwen3-Embedding-8B` + `nvidia/nemotron-3-super-120b-a12b` | Semantic recall, then reasoning over criteria |
| 7 | Tailored application draft (RAG-grounded) | `nvidia/Nemotron-3-Ultra-550b-a55b` | Long-form writing that sticks to the founder's facts |

**RAG.** [`app/knowledge/`](app/knowledge) holds a funding knowledge base: stage benchmarks, how grant panels score, what investors look for, writing guidance, funding types, use of funds and raising in emerging markets. [`app/ai/rag.py`](app/ai/rag.py) splits it into sections, embeds them once with the Token Factory embedding model, and retrieves the closest sections for each step. The review lists the sections it was judged against.

**Behind the AI.** Every model call is logged with its model, latency, tokens and cost. Founders see a clean product. To see the engine, open `/ideas/<id>/trace` while logged in as the idea's owner.

Code: [`app/ai/pipeline.py`](app/ai/pipeline.py) (steps and prompts), [`app/ai/client.py`](app/ai/client.py) (OpenAI-compatible Token Factory client with retries), [`app/ai/research.py`](app/ai/research.py) (Tavily), [`app/ai/rag.py`](app/ai/rag.py).

## Nebius services used

- **Token Factory:** all chat, vision and embedding calls. A single OpenAI-compatible base URL, with an optional per-step override for models served from other regions.
- **Serverless Endpoints:** the app ships as a CPU container ([`Dockerfile`](Dockerfile)). See [`deploy/NEBIUS.md`](deploy/NEBIUS.md).
- **Serverless Jobs:** `python -m app.jobs rematch` re-scores every idea against every program in the background.

## Run it locally

You need Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # add NEBIUS_API_KEY (and optionally TAVILY_API_KEY)
python scripts/seed.py --reset    # demo funders, programs and founders, reviewed by the pipeline
uvicorn app.main:app --port 8110
```

Then open http://localhost:8110.

- **No key yet?** The app runs in *preview mode*: every model call is answered locally by simple heuristics, so the whole product can be clicked through. A small "Preview mode" badge shows when this is on.
- **Check your models:** `python scripts/list_models.py` confirms every configured model is available to your key. Any step's model can be swapped through env vars (see `.env.example`).
- **Demo logins:** founders `founder@example.test`, `founder2@example.test`, `founder3@example.test`; funders `grants@example-green.test`, `invest@example-seed.test`, `programs@example-launchpad.test`. The password is `DEMO_PASSWORD` in [`scripts/seed.py`](scripts/seed.py). All organisations are fictional.

## Stack

FastAPI, Jinja and SQLite, with no front-end build step. Animations use [Motion](https://motion.dev). Model calls run as background tasks, and the page shows live progress. Passwords are hashed with scrypt, sessions use signed cookies. Photos are from [Unsplash](https://unsplash.com) (free licence).

## Feedback on Nebius Token Factory and NVIDIA models

*To be completed after the first full run with live keys.* We'll note: model availability and region differences, latency per model size, JSON reliability per model, embedding quality for matching, and any rough edges in the API or console.

## Built during the submission period

SeedBridge was started and built during the hackathon (October 2026).
