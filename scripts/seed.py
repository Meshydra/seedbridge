"""Load demo accounts, sponsor programs and founder ideas, then run the AI pipeline on each idea.

    python scripts/seed.py           # add demo data (skips if already there)
    python scripts/seed.py --reset   # wipe the database first

All organisations below are fictional ("Example ...") so nobody mistakes them for real funders.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import auth, config, db  # noqa: E402
from app.ai import pipeline  # noqa: E402

DEMO_PASSWORD = "seedbridge-demo"  # demo-only accounts, also listed in the README

SPONSORS = [
    ("grants@example-green.test", "Asha Perera", "Example Green Futures Foundation", [
        dict(name="Climate Resilience Micro-Grant", kind="Grant", min_usd=5000, max_usd=25000,
             sectors="Agriculture, Climate & Energy", stages="Idea, Prototype, MVP", countries="Sri Lanka, India, Bangladesh",
             deadline="2026-12-15",
             description="Non-dilutive grants for early ventures that help farmers and coastal communities adapt to climate change.",
             criteria="Clear beneficiary group, a pilot plan within 6 months, measurable impact (tonnes, hectares, households). Local founding team preferred."),
    ]),
    ("invest@example-seed.test", "Daniel Fernando", "Example Seed Partners", [
        dict(name="Pre-Seed Fund I", kind="Equity investment", min_usd=50000, max_usd=250000,
             sectors="Fintech, Software & AI, Logistics, Retail & E-commerce", stages="MVP, Early revenue", countries="",
             deadline="2027-03-31",
             description="First institutional cheque for software businesses in South Asia with regional ambitions.",
             criteria="Paying customers or strong usage, a technical co-founder, a market that can reach $50M revenue. We lead or co-lead rounds."),
    ]),
    ("programs@example-launchpad.test", "Nimali Silva", "Example Women Founders Launchpad", [
        dict(name="Women Founders Accelerator 2027", kind="Accelerator", min_usd=10000, max_usd=20000,
             sectors="", stages="Prototype, MVP, Early revenue", countries="",
             deadline="2027-01-20",
             description="12-week program with mentoring, investor demo day and a stipend for women-led startups.",
             criteria="At least one woman founder in a leadership role, committed full time, a working prototype."),
        dict(name="Social Innovation Prize", kind="Prize / competition", min_usd=2000, max_usd=15000,
             sectors="Education, Health, Social impact", stages="", countries="Sri Lanka",
             deadline="2026-11-30",
             description="Annual prize for ideas that improve education or health outcomes in underserved communities.",
             criteria="Clear social problem, evidence the approach works, a plan to reach 1,000 people in a year."),
    ]),
]

FOUNDERS = [
    ("founder@example.test", "Kasun Jayawardena", dict(
        title="PaddySense", one_liner="SMS alerts that tell rice farmers when and how much to irrigate, using soil sensors and weather data.",
        sector="Agriculture", stage="Prototype", country="Sri Lanka", ask_usd=20000,
        problem="Smallholder rice farmers in the dry zone over-irrigate early in the season and run short later; tank water allocation is guesswork. Yield losses of 15-25% in drought years are common, and farmers have no simple signal for when to irrigate.",
        solution="Low-cost soil moisture sensors (under $30 each) shared across a farmer group, combined with Department of Meteorology forecasts. Farmers receive a Sinhala SMS with an irrigation recommendation every two days.",
        business_model="Farmer organisations pay $3 per farmer per season; agro-input companies sponsor sensors in exchange for advisory slots.",
        team="Kasun (agricultural engineer, 6 years with irrigation department), Tharindu (embedded systems developer).",
        traction="Pilot with 40 farmers in Anuradhapura during Yala 2026: 18% water saving reported by the farmer organisation.",
        use_of_funds="200 sensors, SMS costs for 2 seasons, field officer for onboarding 500 farmers.")),
    ("founder2@example.test", "Ruwani Dissanayake", dict(
        title="LedgerLite", one_liner="Voice-first bookkeeping for small shops: say the sale, get the books.",
        sector="Fintech", stage="Early revenue", country="Sri Lanka", ask_usd=150000,
        problem="Most small retailers keep credit and sales in paper books. They can't show income to banks, so they can't get working-capital loans.",
        solution="An Android app where shop owners record sales and customer credit by voice in Sinhala, Tamil or English. Monthly statements are formatted for bank loan applications.",
        business_model="Freemium; $4/month for statements and reminders. Revenue share with partner banks on loans originated.",
        team="Ruwani (ex-product manager at a payments company), co-founder CTO with 8 years in mobile development.",
        traction="2,300 active shops, 410 paying, $1,600 monthly recurring revenue growing 12% month on month. Pilot with one regional bank.",
        use_of_funds="Hire 3 engineers and 2 field sales staff; expand to Tamil Nadu.")),
    ("founder3@example.test", "Imran Farook", dict(
        title="ClassBridge", one_liner="Recorded O/L science lessons that run offline on cheap tablets for rural schools.",
        sector="Education", stage="Idea", country="Sri Lanka", ask_usd=8000,
        problem="Rural schools lack qualified science teachers.",
        solution="Offline tablet lessons.",
        business_model="", team="", traction="", use_of_funds="Tablets and content.")),
]


def main():
    if "--reset" in sys.argv and config.DB_PATH.exists():
        for suffix in ("", "-wal", "-shm"):
            Path(str(config.DB_PATH) + suffix).unlink(missing_ok=True)
    db.init()
    if db.one("SELECT id FROM users WHERE email = ?", SPONSORS[0][0]):
        print("Demo data already loaded (use --reset to start over).")
        return

    for email, name, org, programs in SPONSORS:
        uid = db.run("INSERT INTO users (email, name, role, org, password_hash, created_at) VALUES (?,?,?,?,?,?)",
                     email, name, "sponsor", org, auth.hash_password(DEMO_PASSWORD), db.now())
        for p in programs:
            cols = list(p) + ["sponsor_id", "created_at"]
            db.run(f"INSERT INTO programs ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                   *p.values(), uid, db.now())

    for email, name, idea in FOUNDERS:
        uid = db.run("INSERT INTO users (email, name, role, org, password_hash, created_at) VALUES (?,?,?,?,?,?)",
                     email, name, "founder", None, auth.hash_password(DEMO_PASSWORD), db.now())
        cols = list(idea) + ["user_id", "share", "status", "created_at", "updated_at"]
        idea_id = db.run(f"INSERT INTO ideas ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         *idea.values(), uid, 1, "pending", db.now(), db.now())
        print(f"Reviewing {idea['title']} ...", flush=True)
        pipeline.process_idea(idea_id)
        print("  ->", db.one("SELECT status FROM ideas WHERE id=?", idea_id)["status"])

    print(f"\nDone ({'demo mode' if config.DEMO_MODE else 'live Nebius models'}). "
          f"Log in as founder@example.test or grants@example-green.test; password in scripts/seed.py.")


if __name__ == "__main__":
    main()
