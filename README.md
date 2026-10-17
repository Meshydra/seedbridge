# SeedBridge

**Founders describe a business idea once. A team of NVIDIA Nemotron models reviews it the way a grant panel would and matches it to the grants, funds, prizes and accelerators it fits. Sponsors publish programs and get a ranked, pre-reviewed shortlist.**

Built for the Nebius x NVIDIA Global AI Hackathon on Devpost (Best Apps and Agents track). It runs on NVIDIA open models served by **Nebius Token Factory**.

## The problem

Early founders, especially outside the big startup hubs, rarely know which funding they're eligible for, and they write their applications blind. Sponsors receive piles of unsuitable applications and screen them by hand. Both sides waste weeks.

## What it does

**For founders**
- A guided form covers problem, solution, business model, team, traction, ask and use of funds. You can attach your strongest pitch-deck slide.
- An **investor-readiness review** scores six dimensions out of 10, then lists strengths, risks and the three edits that will raise the score most.
- **"What a panel will ask"** lists the missing information and the follow-up questions to prepare for.
- **Matched programs** are ranked by fit, with eligibility problems flagged up front: wrong stage, wrong country, ask out of range, deadline passed.
- **One-click application drafts** are tailored to a program. Missing facts are marked `[ADD: …]` instead of being invented.
- Founders choose whether matched sponsors can see an idea.

**For sponsors**
- Publish a grant, equity fund, prize, accelerator or loan with criteria, ticket size, sectors, stages and countries.
- Every shared idea is scored against the program as soon as it's published. Sponsors see a ranked list, the reason for each match and the full review.
- Applications arrive pre-reviewed. Sponsors can shortlist, decline or request an intro; requesting an intro shares contact details with both sides.

## How it uses NVIDIA models on Nebius Token Factory

Each step uses the smallest model that does that job well, and only the hard reasoning goes to Ultra.

| Step | Model (Token Factory ID) | Why |
|---|---|---|
| Structure the application | `nvidia/Nemotron-3_5-Lightning` | Runs on every submission, so it needs to be fast and cheap |
| Find missing information | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Checklist-style analysis |
| Read pitch-deck slide | `nvidia/Nemotron-3.5-Super-VL` | Vision: pulls out claims and numbers and checks them against the written answers |
| Shortlist programs | `Qwen/Qwen3-Embedding-8B` + rule checks | Semantic similarity plus hard eligibility rules |
| Rank and explain matches | `nvidia/nemotron-3-super-120b-a12b` | Reasons over the criteria and writes a specific explanation |
| Investor-readiness review | `nvidia/Nemotron-3-Ultra-550b-a55b` | The deepest judgement in the app |
| Application drafts | `nvidia/Nemotron-3-Ultra-550b-a55b` | Long-form writing grounded in the founder's own facts |

Every idea page has a **"How the models worked on this"** table showing the model, latency, tokens and cost of each call. Costs use Token Factory's published per-token prices.

Code: [`app/ai/pipeline.py`](app/ai/pipeline.py) (steps and prompts) and [`app/ai/client.py`](app/ai/client.py) (the OpenAI-compatible Token Factory client).

## Run it locally

You need Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # add NEBIUS_API_KEY, or leave it empty for demo mode
python scripts/seed.py --reset    # demo sponsors, programs and founders
uvicorn app.main:app --port 8110
```

Then open http://localhost:8110.

**Demo mode:** with no `NEBIUS_API_KEY`, every model call is answered locally by simple heuristics. The whole app works without credits, and a banner says it's simulated. Add a key to use the real Nemotron models.

**Check your models:** `python scripts/list_models.py` confirms every configured model ID is available to your key. Any step's model can be swapped through env vars (see `.env.example`).

**Demo logins** (local seed data only; every organisation is fictional):

| Role | Email |
|---|---|
| Founder | `founder@example.test` (also `founder2@`, `founder3@`) |
| Sponsor | `grants@example-green.test`, `invest@example-seed.test`, `programs@example-launchpad.test` |

The password is `DEMO_PASSWORD` in [`scripts/seed.py`](scripts/seed.py).

## Stack

FastAPI, Jinja templates and SQLite, with no front-end build step. Model calls run as background tasks, and the page shows live progress through the pipeline. Passwords are hashed with scrypt, sessions use signed cookies.

## Roadmap

- Deploy on Nebius Serverless Endpoints, and run matching as a Nebius Serverless Job.
- Live program discovery with web search.
- Sinhala and Tamil interfaces and reviews.
- Deck upload as PDF (multi-slide).

## Licence

[MIT](LICENSE)
