"""Background work meant to run as a Nebius Serverless Job (or any cron).

    python -m app.jobs rematch   # re-score every shared idea against every program
    python -m app.jobs pending   # review ideas stuck in 'pending' (e.g. after a restart)
"""
import sys

from . import db
from .ai import pipeline


def rematch():
    db.init()
    ideas = db.all_("SELECT id, title FROM ideas WHERE status='done' AND share=1")
    for idea in ideas:
        print(f"matching {idea['title']}", flush=True)
        pipeline.match_idea(idea["id"])
    print(f"rematched {len(ideas)} ideas")


def pending():
    db.init()
    ideas = db.all_("SELECT id, title FROM ideas WHERE status IN ('pending','running')")
    for idea in ideas:
        print(f"reviewing {idea['title']}", flush=True)
        pipeline.process_idea(idea["id"])
    print(f"reviewed {len(ideas)} ideas")


if __name__ == "__main__":
    {"rematch": rematch, "pending": pending}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
