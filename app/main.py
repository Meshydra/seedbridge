"""SeedBridge web app: founders submit ideas, Nemotron models review and match them, sponsors list programs."""
import json
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, db
from .ai import pipeline

HERE = Path(__file__).resolve().parent
app = FastAPI(title="SeedBridge")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY, same_site="lax", max_age=60 * 60 * 24 * 14)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["loads"] = lambda v, d=None: db.loads(v, d)
templates.env.filters["money"] = lambda v: f"${int(v):,}" if v not in (None, "") else "—"

STEP_LABELS = {
    "intake": "Structure the application", "gaps": "Find missing information",
    "vision": "Read pitch-deck slide", "review": "Investor-readiness review",
    "embed": "Semantic embedding", "match": "Rank sponsor matches", "draft": "Draft application",
}
templates.env.globals.update(config=config, STEP_LABELS=STEP_LABELS)

db.init()


@app.exception_handler(auth.LoginRequired)
async def _login_redirect(request: Request, exc):
    return RedirectResponse("/login?next=" + request.url.path, status_code=303)


def render(request: Request, name: str, **ctx):
    ctx.setdefault("user", auth.current_user(request))
    ctx["flash"] = request.session.pop("flash", None)
    return templates.TemplateResponse(request, name, ctx)


def back(url: str, flash: str | None = None, request: Request | None = None):
    if flash and request is not None:
        request.session["flash"] = flash
    return RedirectResponse(url, status_code=303)


def _int(value):
    try:
        return int(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- public + auth

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    stats = {
        "ideas": db.one("SELECT COUNT(*) n FROM ideas")["n"],
        "programs": db.one("SELECT COUNT(*) n FROM programs")["n"],
        "sponsors": db.one("SELECT COUNT(*) n FROM users WHERE role='sponsor'")["n"],
    }
    return render(request, "index.html", stats=stats)


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request, role: str = "founder"):
    return render(request, "auth.html", mode="signup", role=role if role in ("founder", "sponsor") else "founder")


@app.post("/signup")
def signup(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...),
           role: str = Form("founder"), org: str = Form("")):
    email = email.strip().lower()
    if role not in ("founder", "sponsor"):
        raise HTTPException(400)
    if len(password) < 8:
        return render(request, "auth.html", mode="signup", role=role, error="Use at least 8 characters.")
    if db.one("SELECT id FROM users WHERE email = ?", email):
        return render(request, "auth.html", mode="signup", role=role, error="That email already has an account.")
    uid = db.run("INSERT INTO users (email, name, role, org, password_hash, created_at) VALUES (?,?,?,?,?,?)",
                 email, name.strip(), role, org.strip() or None, auth.hash_password(password), db.now())
    request.session["uid"] = uid
    return back("/programs/new" if role == "sponsor" else "/ideas/new")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/dashboard"):
    return render(request, "auth.html", mode="login", next=next)


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form("/dashboard")):
    row = db.one("SELECT * FROM users WHERE email = ?", email.strip().lower())
    if not row or not auth.check_password(password, row["password_hash"]):
        return render(request, "auth.html", mode="login", next=next, error="Wrong email or password.")
    request.session["uid"] = row["id"]
    return back(next if next.startswith("/") and not next.startswith("//") else "/dashboard")


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return back("/")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = auth.require(request)
    if user["role"] == "sponsor":
        programs = db.all_(
            "SELECT p.*, (SELECT COUNT(*) FROM matches m JOIN ideas i ON i.id=m.idea_id"
            "  WHERE m.program_id=p.id AND i.share=1 AND m.fit_score>=50) AS strong,"
            " (SELECT COUNT(*) FROM applications a WHERE a.program_id=p.id AND a.status IN ('submitted','shortlisted','intro')) AS apps"
            " FROM programs p WHERE sponsor_id=? ORDER BY id DESC", user["id"])
        return render(request, "sponsor_dashboard.html", programs=programs)
    ideas = db.all_(
        "SELECT i.*, (SELECT MAX(fit_score) FROM matches m WHERE m.idea_id=i.id) AS best_fit,"
        " (SELECT COUNT(*) FROM matches m WHERE m.idea_id=i.id) AS n_matches"
        " FROM ideas i WHERE user_id=? ORDER BY id DESC", user["id"])
    return render(request, "founder_dashboard.html", ideas=ideas)


# ---------------------------------------------------------------- founders

IDEA_FIELDS = ["title", "one_liner", "problem", "solution", "sector", "stage", "country",
               "business_model", "team", "traction", "use_of_funds"]


def _own_idea(user, idea_id):
    idea = db.one("SELECT * FROM ideas WHERE id = ?", idea_id)
    if not idea or idea["user_id"] != user["id"]:
        raise HTTPException(404)
    return idea


@app.get("/ideas/new", response_class=HTMLResponse)
def idea_new(request: Request):
    auth.require(request, "founder")
    return render(request, "idea_form.html", idea={}, action="/ideas/new")


@app.get("/ideas/{idea_id}/edit", response_class=HTMLResponse)
def idea_edit(request: Request, idea_id: int):
    user = auth.require(request, "founder")
    return render(request, "idea_form.html", idea=_own_idea(user, idea_id), action=f"/ideas/{idea_id}/edit")


async def _save_deck(deck: UploadFile | None):
    if not deck or not deck.filename:
        return None
    ext = Path(deck.filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "Upload the key pitch-deck slide as PNG, JPG or WebP.")
    data = await deck.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Slide image must be under 5 MB.")
    path = config.UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    return str(path)


async def _idea_values(request: Request):
    form = await request.form()
    values = {k: (form.get(k) or "").strip() or None for k in IDEA_FIELDS}
    values["ask_usd"] = _int(form.get("ask_usd"))
    values["share"] = 1 if form.get("share") else 0
    if not values["title"]:
        raise HTTPException(400, "Title is required.")
    deck = form.get("deck")
    return values, await _save_deck(deck if hasattr(deck, "filename") else None)


@app.post("/ideas/new")
async def idea_create(request: Request, tasks: BackgroundTasks):
    user = auth.require(request, "founder")
    values, deck_path = await _idea_values(request)
    cols = list(values) + ["deck_path", "user_id", "status", "created_at", "updated_at"]
    idea_id = db.run(f"INSERT INTO ideas ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                     *values.values(), deck_path, user["id"], "pending", db.now(), db.now())
    tasks.add_task(pipeline.process_idea, idea_id)
    return back(f"/ideas/{idea_id}")


@app.post("/ideas/{idea_id}/edit")
async def idea_update(request: Request, idea_id: int, tasks: BackgroundTasks):
    user = auth.require(request, "founder")
    idea = _own_idea(user, idea_id)
    values, deck_path = await _idea_values(request)
    values["deck_path"] = deck_path or idea["deck_path"]
    sets = ", ".join(f"{k}=?" for k in values)
    db.run(f"UPDATE ideas SET {sets}, status='pending', updated_at=? WHERE id=?", *values.values(), db.now(), idea_id)
    tasks.add_task(pipeline.process_idea, idea_id)
    return back(f"/ideas/{idea_id}", "Saved. The models are re-reviewing your idea.", request)


def _steps(idea_id, application_id=None):
    if application_id:
        return db.all_("SELECT * FROM ai_steps WHERE application_id=? ORDER BY id", application_id)
    return db.all_("SELECT * FROM ai_steps WHERE idea_id=? AND application_id IS NULL ORDER BY id", idea_id)


@app.get("/ideas/{idea_id}", response_class=HTMLResponse)
def idea_view(request: Request, idea_id: int):
    user = auth.require(request, "founder")
    idea = _own_idea(user, idea_id)
    matches = db.all_(
        "SELECT m.*, p.name, p.kind, p.min_usd, p.max_usd, p.deadline, u.org AS sponsor_org, u.name AS sponsor_name,"
        " a.id AS application_id, a.status AS application_status"
        " FROM matches m JOIN programs p ON p.id=m.program_id JOIN users u ON u.id=p.sponsor_id"
        " LEFT JOIN applications a ON a.idea_id=m.idea_id AND a.program_id=m.program_id"
        " WHERE m.idea_id=? ORDER BY m.fit_score DESC", idea_id)
    return render(request, "idea.html", idea=idea, matches=matches, steps=_steps(idea_id))


@app.get("/ideas/{idea_id}/status")
def idea_status(request: Request, idea_id: int):
    user = auth.require(request, "founder")
    idea = _own_idea(user, idea_id)
    return JSONResponse({"status": idea["status"],
                         "steps": [{"step": s["step"], "status": s["status"]} for s in _steps(idea_id)]})


@app.post("/ideas/{idea_id}/rerun")
def idea_rerun(request: Request, idea_id: int, tasks: BackgroundTasks):
    user = auth.require(request, "founder")
    _own_idea(user, idea_id)
    db.run("UPDATE ideas SET status='pending' WHERE id=?", idea_id)
    tasks.add_task(pipeline.process_idea, idea_id)
    return back(f"/ideas/{idea_id}")


@app.post("/ideas/{idea_id}/share")
def idea_share(request: Request, idea_id: int):
    user = auth.require(request, "founder")
    idea = _own_idea(user, idea_id)
    db.run("UPDATE ideas SET share=? WHERE id=?", 0 if idea["share"] else 1, idea_id)
    return back(f"/ideas/{idea_id}", "Sharing updated.", request)


@app.post("/ideas/{idea_id}/apply/{program_id}")
def idea_apply(request: Request, idea_id: int, program_id: int, tasks: BackgroundTasks):
    user = auth.require(request, "founder")
    _own_idea(user, idea_id)
    if not db.one("SELECT id FROM programs WHERE id=?", program_id):
        raise HTTPException(404)
    existing = db.one("SELECT id FROM applications WHERE idea_id=? AND program_id=?", idea_id, program_id)
    if existing:
        return back(f"/applications/{existing['id']}")
    app_id = db.run("INSERT INTO applications (idea_id, program_id, status, created_at, updated_at)"
                    " VALUES (?,?,?,?,?)", idea_id, program_id, "drafting", db.now(), db.now())
    tasks.add_task(pipeline.draft_application, app_id)
    return back(f"/applications/{app_id}")


# ---------------------------------------------------------------- applications (both sides)

def _application_for(user, app_id):
    row = db.one(
        "SELECT a.*, i.title AS idea_title, i.user_id AS founder_id, i.share, p.name AS program_name, p.kind,"
        " p.sponsor_id, u.org AS sponsor_org, u.name AS sponsor_name, u.email AS sponsor_email,"
        " f.name AS founder_name, f.email AS founder_email"
        " FROM applications a JOIN ideas i ON i.id=a.idea_id JOIN programs p ON p.id=a.program_id"
        " JOIN users u ON u.id=p.sponsor_id JOIN users f ON f.id=i.user_id WHERE a.id=?", app_id)
    if not row:
        raise HTTPException(404)
    if user["id"] == row["founder_id"]:
        return row, "founder"
    if user["id"] == row["sponsor_id"] and row["status"] not in ("drafting", "draft", "error"):
        return row, "sponsor"
    raise HTTPException(404)


@app.get("/applications/{app_id}", response_class=HTMLResponse)
def application_view(request: Request, app_id: int):
    user = auth.require(request)
    row, side = _application_for(user, app_id)
    return render(request, "application.html", a=row, side=side, steps=_steps(row["idea_id"], app_id))


@app.get("/applications/{app_id}/status")
def application_status(request: Request, app_id: int):
    user = auth.require(request)
    row, _ = _application_for(user, app_id)
    return JSONResponse({"status": row["status"]})


@app.post("/applications/{app_id}")
def application_save(request: Request, app_id: int, draft: str = Form(...), action: str = Form("save")):
    user = auth.require(request, "founder")
    row, side = _application_for(user, app_id)
    if row["status"] not in ("draft", "error"):
        return back(f"/applications/{app_id}", "This application was already sent.", request)
    status = "submitted" if action == "submit" else "draft"
    db.run("UPDATE applications SET draft=?, status=?, updated_at=? WHERE id=?", draft, status, db.now(), app_id)
    return back(f"/applications/{app_id}", "Sent to the sponsor." if status == "submitted" else "Draft saved.", request)


@app.post("/applications/{app_id}/decision")
def application_decision(request: Request, app_id: int, decision: str = Form(...), note: str = Form("")):
    user = auth.require(request, "sponsor")
    row, side = _application_for(user, app_id)
    if decision not in ("shortlisted", "intro", "declined"):
        raise HTTPException(400)
    db.run("UPDATE applications SET status=?, sponsor_note=?, updated_at=? WHERE id=?",
           decision, note.strip() or None, db.now(), app_id)
    return back(f"/applications/{app_id}", "Decision saved; the founder can see it.", request)


# ---------------------------------------------------------------- sponsors

PROGRAM_FIELDS = ["name", "kind", "description", "criteria", "deadline"]


@app.get("/programs/new", response_class=HTMLResponse)
def program_new(request: Request):
    auth.require(request, "sponsor")
    return render(request, "program_form.html", p={})


@app.post("/programs/new")
async def program_create(request: Request, tasks: BackgroundTasks):
    user = auth.require(request, "sponsor")
    form = await request.form()
    values = {k: (form.get(k) or "").strip() or None for k in PROGRAM_FIELDS}
    if not values["name"] or values["kind"] not in config.PROGRAM_KINDS:
        raise HTTPException(400, "Name and type are required.")
    values["min_usd"], values["max_usd"] = _int(form.get("min_usd")), _int(form.get("max_usd"))
    values["sectors"] = ", ".join(form.getlist("sectors")) or None
    values["stages"] = ", ".join(form.getlist("stages")) or None
    values["countries"] = (form.get("countries") or "").strip() or None
    cols = list(values) + ["sponsor_id", "created_at"]
    pid = db.run(f"INSERT INTO programs ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                 *values.values(), user["id"], db.now())
    tasks.add_task(pipeline.match_program, pid)
    return back(f"/programs/{pid}", "Program published. Matching it against founders now.", request)


def _own_program(user, pid):
    p = db.one("SELECT * FROM programs WHERE id=?", pid)
    if not p or p["sponsor_id"] != user["id"]:
        raise HTTPException(404)
    return p


@app.get("/programs/{pid}", response_class=HTMLResponse)
def program_view(request: Request, pid: int):
    user = auth.require(request, "sponsor")
    p = _own_program(user, pid)
    matches = db.all_(
        "SELECT m.*, i.title, i.one_liner, i.sector, i.stage, i.country, i.ask_usd, i.review_json"
        " FROM matches m JOIN ideas i ON i.id=m.idea_id WHERE m.program_id=? AND i.share=1"
        " ORDER BY m.fit_score DESC", pid)
    apps = db.all_(
        "SELECT a.*, i.title FROM applications a JOIN ideas i ON i.id=a.idea_id"
        " WHERE a.program_id=? AND a.status NOT IN ('drafting','draft','error') ORDER BY a.updated_at DESC", pid)
    return render(request, "program.html", p=p, matches=matches, apps=apps)


@app.get("/programs/{pid}/ideas/{idea_id}", response_class=HTMLResponse)
def program_idea(request: Request, pid: int, idea_id: int):
    """Sponsor's view of a matched idea: only if the founder shares it and it matched this program."""
    user = auth.require(request, "sponsor")
    p = _own_program(user, pid)
    idea = db.one("SELECT i.*, u.name AS founder_name FROM ideas i JOIN users u ON u.id=i.user_id"
                  " WHERE i.id=? AND i.share=1", idea_id)
    match = db.one("SELECT * FROM matches WHERE idea_id=? AND program_id=?", idea_id, pid)
    if not idea or not match:
        raise HTTPException(404)
    return render(request, "sponsor_idea.html", p=p, idea=idea, match=match)
