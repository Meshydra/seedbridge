# Devpost submission draft

**Track:** Best Apps and Agents

**Tagline:** Describe your idea once. Get funding-ready, and get matched to the funders who fit.

## Inspiration

Founders outside the big startup hubs rarely know which grants or investors they're eligible for, and they write applications blind. Most rejections are avoidable: wrong funder, wrong stage, a missing number. Funders, meanwhile, screen piles of unsuitable applications by hand. We wanted one place where both sides meet, already prepared.

## What it does

Founders fill in a friendly five-step form, including where the business is: just an idea, pre-seed, seed, Series A+ or a live business. SeedBridge then:
- scores readiness across six dimensions against what funders expect at that stage;
- lists the questions a panel will ask;
- researches the market live, with sources;
- ranks matching funders, with eligibility problems flagged;
- drafts a tailored application in one click, using only the founder's own facts.

Funders publish programs and get a ranked, pre-reviewed shortlist. They can then shortlist, decline or request an intro.

## How we built it

- **NVIDIA Nemotron on Nebius Token Factory, five models with one job each:**
  - Nemotron 3.5 Lightning structures applications and writes research queries.
  - Nemotron 3 Nano finds the gaps.
  - Nemotron 3.5 Super VL reads pitch slides.
  - Nemotron 3 Super reranks and explains funder matches.
  - Nemotron 3 Ultra writes the readiness review and the application drafts.
  - Qwen3 Embedding 8B on Token Factory powers matching and retrieval.
- **RAG** over a funding knowledge base (stage benchmarks, grant-panel criteria, investor criteria, writing guidance), so reviews are judged against the right yardstick for the founder's stage, and cite it.
- **Tavily** web search for live market research; Lightning summarises it with sources.
- **Nebius Serverless Endpoints** host the app as a CPU container. A **Nebius Serverless Job** re-matches every idea against every program in the background.
- FastAPI, SQLite, Jinja and Motion (motion.dev) for animation.

## Challenges

- Making every model return reliable JSON.
- Keeping drafts honest: missing facts become `[ADD: …]` and are never invented.
- Choosing the smallest model for each job, so a full review stays cheap and fast.

## What's next

- Sinhala and Tamil reviews.
- Multi-slide PDF decks.
- A larger verified catalogue of real funding programs.
- Funder analytics.

## Feedback for Nebius and NVIDIA

(Fill in after the live run.)

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
| 2:30–2:55 | `/trace` page: models, latency, cost | "Under the hood: Lightning, Nano, Super VL, Super and Ultra, plus embeddings. Each review costs a fraction of a dollar." |
| 2:55–3:00 | Logo | "SeedBridge. Built on Nebius and NVIDIA." |
