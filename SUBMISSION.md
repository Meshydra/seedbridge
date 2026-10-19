# Devpost submission

Field-by-field answers for the Nebius x NVIDIA Global AI Hackathon form, in the order Devpost asks for them.
Lines marked **TODO** need a person (a personal detail, a live run, or a link that doesn't exist yet).

---

## 1. Project overview

**Project name** (60 max)

> SeedBridge

**Elevator pitch** (200 max)

> Describe your business idea once. SeedBridge reviews it like a funding panel, shows what to fix, and matches you to the grants, investors and accelerators you actually fit.

**Thumbnail** (3:2): `docs/screenshots/1-landing.png`

---

## 2. Project details

### About the project

```markdown
## Inspiration

Founders outside the big startup hubs rarely know which grants or investors they're eligible for, so they write applications blind. Most rejections are avoidable: the wrong funder, the wrong stage, a missing number, a budget that doesn't add up. Funders face the mirror image, screening piles of unsuitable applications by hand. We wanted one place where both sides meet already prepared.

## What it does

**Founders** describe their idea once in a five-step form, including where the business is now: just an idea, pre-seed, seed, Series A+ or a live business. SeedBridge then:

- scores **funding readiness** out of 100 across six dimensions, judged against what funders expect *at that stage*, with strengths, risks and the three fixes that matter most;
- lists **what a panel will ask**: the missing information and the questions to prepare for;
- builds a **market snapshot** from live web research, with sources;
- ranks **matching funders** by fit and flags eligibility problems before you waste time applying;
- writes a **tailored application** in one click, using only the founder's own facts. Anything missing is marked `[ADD: …]`, never invented.

**Funders** list a grant, equity fund, prize, accelerator or loan, then get a ranked, pre-reviewed shortlist of founders who fit, each with the reason. They can shortlist, decline or request an intro.

## How we built it

Seven AI steps, each on the smallest NVIDIA Nemotron model that does the job well, all served by **Nebius Token Factory**:

| Step | Model |
|---|---|
| Structure the application, write research queries | Nemotron 3.5 Lightning |
| Market research (Tavily search, summarised with sources) | Tavily + Nemotron 3.5 Lightning |
| What a panel will ask | Nemotron 3 Nano 30B-A3B |
| Read the pitch slide | Nemotron 3.5 Super VL |
| Readiness review | Nemotron 3 Ultra 550B-A55B |
| Match funders: embeddings + hard rules, then rerank and explain | Qwen3 Embedding 8B + Nemotron 3 Super 120B-A12B |
| Tailored application draft | Nemotron 3 Ultra 550B-A55B |

- **RAG** over a funding knowledge base we wrote (stage benchmarks, how grant panels score, what investors look for, writing guidance, raising in emerging markets). Each review lists the sections it was judged against.
- **Matching** is hybrid: hard eligibility rules (stage, sector, country, ticket size) and embedding similarity build a shortlist, then Nemotron Super reranks it and explains every match in one sentence.
- **Behind the AI** page: every model call is logged with model, latency, tokens and cost, so a full review is auditable and costs a fraction of a cent.
- **Nebius Serverless**: the app ships as a CPU container for a Serverless Endpoint, and re-matching runs as a Serverless Job.
- FastAPI, Jinja and SQLite with no front-end build step; Motion for animation. Model calls run as background tasks with live progress.

## Challenges we ran into

- **Reliable JSON from every model size.** We parse defensively (fenced blocks, stray reasoning) and retry, so one malformed answer never breaks a review.
- **Keeping drafts honest.** Application drafts may only use the founder's facts; gaps become `[ADD: …]` placeholders.
- **Right-sizing models.** Running Ultra everywhere would be slow and expensive. Splitting the work across Lightning, Nano, Super and Ultra kept a full review fast and cheap without losing quality where it matters.
- **Stage-aware judgement.** A pre-seed idea and a trading business shouldn't be scored against the same bar, so the review retrieves benchmarks for the founder's stage first.

## What we learned

- Small, fast models handle structuring and checklists well; the big model earns its cost only for judgement and long-form writing.
- Grounding with a short, well-written knowledge base improved consistency more than longer prompts did.
- Showing founders *why* (cited benchmarks, flagged eligibility rules) builds more trust than a bare score.

## What's next

- Sinhala and Tamil reviews.
- Multi-slide PDF decks.
- A larger, verified catalogue of real funding programs.
- Real OAuth for LinkedIn, GitHub and Google, and funder analytics.
```

### Built with (up to 25 tags)

> python, fastapi, jinja, sqlite, uvicorn, httpx, nvidia-nemotron, nemotron-3-ultra, nemotron-3-super, nemotron-3-nano, nemotron-3.5-lightning, nemotron-3.5-super-vl, qwen3-embedding, nebius, nebius-token-factory, nebius-serverless, tavily, rag, docker, motion, html, css, javascript

### "Try it out" links

- Code: https://github.com/Meshydra/seedbridge
- Live demo: **TODO** (Nebius Serverless Endpoint URL, see `deploy/NEBIUS.md`)

### Image gallery (3:2, upload in this order)

1. `docs/screenshots/1-landing.png`
2. `docs/screenshots/2-idea-form.png`
3. `docs/screenshots/3-readiness-review.png`
4. `docs/screenshots/4-matched-funders.png`
5. `docs/screenshots/5-application-draft.png`
6. `docs/screenshots/6-funder-shortlist.png`
7. `docs/screenshots/7-funder-founder-view.png`
8. `docs/screenshots/8-behind-the-ai.png` (re-capture after the live run so the "simulated" badges are gone)

### Demo video URL

**TODO**: YouTube or Vimeo, public or unlisted, under 3 minutes. Script at the end of this file.

---

## 3. Additional info (judges and organisers only)

**Upload a file:** optional. Skip, or upload a zip of the repo.

**Submitter type:** **TODO** (Individual / Team / Organization)

**Organization name:** **TODO** ("N/A" if not representing an organisation)

**Country of residence:** **TODO**

**Canadian province:** N/A

**Track:** Best apps and agents

**New or existing before 26 August 2026?** New. Started and built during the hackathon (October 2026).

**Public code repository:** https://github.com/Meshydra/seedbridge (MIT licence, README with setup, Nemotron and Nebius usage)

**Working demo URL:** **TODO** (Nebius Serverless Endpoint)

**Which model(s) did you use, and why that size/variant?**

> Five Nemotron models, each on the smallest size that does its job well, all on Nebius Token Factory:
> - **Nemotron 3.5 Lightning** structures every submission and writes web-search queries, then summarises Tavily results. It runs on every submission, so it has to be fast and cheap.
> - **Nemotron 3 Nano 30B-A3B** does the checklist-style gap analysis ("what a panel will ask"). A small MoE is enough for a structured completeness check.
> - **Nemotron 3.5 Super VL** reads the pitch slide and checks its claims and numbers against the written answers. We needed vision.
> - **Nemotron 3 Super 120B-A12B** reranks the funder shortlist and explains each match. It reasons over eligibility criteria without Ultra's cost.
> - **Nemotron 3 Ultra 550B-A55B** writes the readiness review and the tailored application drafts: the deepest judgement and the longest writing in the product.
> - **Qwen3 Embedding 8B** (also on Token Factory) embeds ideas, programs and the knowledge base for matching and RAG.
>
> Every step's model is configurable through an env var, so we can swap sizes as the catalogue changes.

**Rate Nemotron's output quality (1–10):** **TODO** after the live run. Notes to cover: JSON reliability per size, how well Ultra stuck to "only the founder's facts", Super's match explanations, VL on dense slides.

**Fine-tuned, prompt-engineered, or out of the box?**

> Out of the box, with prompt engineering and retrieval. No fine-tuning. Each step has its own system prompt and a strict JSON output shape. Reviews and drafts are grounded with RAG over a funding knowledge base we wrote, retrieved per step and per funding stage, and the review cites the sections it used. Drafts are constrained to the founder's own facts, with missing items marked `[ADD: …]`. A defensive JSON parser plus retries handle malformed output.

**How did Nemotron compare to other models you've used for similar tasks?** **TODO** after the live run.

**Most valuable Nebius capabilities, and how?**

> - **Token Factory** is the core: one OpenAI-compatible API gives us chat, vision and embeddings across five Nemotron sizes plus Qwen3 Embedding, so mixing model sizes per step was a config change, not an integration. We log latency, tokens and cost per call to show what each review costs. A per-step base-URL override lets a step use a model served from another region.
> - **Serverless Endpoints** host the web app as a small CPU container (all GPU work is in Token Factory, so the app needs no GPU).
> - **Serverless Jobs** run `python -m app.jobs rematch` to re-score every idea against every program in the background.

**Recommend running Nemotron on Nebius (1–10):** **TODO** after the live run and deploy.

**Experience vs previous cloud or local environments (1–10):** **TODO** after the live run and deploy.

**What would have made it more effective?** **TODO** after the live run. Candidates: a guaranteed JSON / structured-output mode on every model, clearer per-region model availability, and a cost estimate per request in the console.

**What do you most hope to see from the Nemotron team next?**

> Native structured output (JSON schema) across every size, stronger multilingual quality for South Asian languages such as Sinhala and Tamil, and multi-page document understanding in the VL model so whole pitch decks can be read in one call.

**Did you use Tavily?** Yes. `app/ai/research.py` calls the Tavily Search API at runtime for each idea's market research; Lightning summarises the results with sources. (Needs `TAVILY_API_KEY` set on the deployed endpoint.)

**Builders & Brews IRL city:** leave blank (no IRL event).

**Age of majority / not an employee of the promotion entities:** **TODO** tick both yourself.

**AI tools used:**

> Claude Code (Anthropic) for coding help, NVIDIA Nemotron models on Nebius Token Factory inside the product, and Tavily for web search.

**Level of learning:** Significant

**Did you gain AI value you can use in your career?** Yes

---

## 3-minute video script

| Time | Shot | Voice-over |
|---|---|---|
| 0:00–0:15 | Landing page animating in | "Most funding applications fail for avoidable reasons. SeedBridge fixes that." |
| 0:15–0:45 | Founder signs up, goes through the wizard, picks "Pre-seed" | "Describe your idea once, including where you are: idea, pre-seed, seed or a live business." |
| 0:45–1:05 | Progress screen ticking through steps | "Five Nemotron models on Nebius Token Factory get to work, each on the job it's best at." |
| 1:05–1:40 | Readiness ring, dimensions, fixes, market snapshot with sources | "An honest score against what funders expect at your stage, grounded in our funding knowledge base and live Tavily research." |
| 1:40–2:05 | Matches with eligibility chips, then "Write my application" and the draft | "Ranked funders, problems flagged up front, and a tailored application from your own facts." |
| 2:05–2:30 | Funder view: ranked founders, request intro | "Funders get a shortlist, not a slush pile." |
| 2:30–2:55 | `/trace` page: models, latency, cost | "Under the hood: Lightning, Nano, Super VL, Super and Ultra, plus embeddings. Each review costs a fraction of a cent." |
| 2:55–3:00 | Logo | "SeedBridge. Built on Nebius and NVIDIA." |
