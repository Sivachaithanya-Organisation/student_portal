import os
import calendar as pycal
from datetime import date, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# ---- Users (guest only for now; swap for a DB / SSO later) -----------------
USERS = {
    "guest": {
        "password": "guest",
        "name": "Guest Student",
        "roll": "GUEST-0001",
        "program": "B.Tech Computer Science",
        "semester": 5,
    }
}


def d(offset):
    return date.today() + timedelta(days=offset)


# ---- Demo data (dates are relative to today so the demo never goes stale) --
EXAMS = [
    {"code": "CS501", "subject": "Operating Systems", "date": d(4), "time": "10:00", "duration": "3 hrs", "room": "Hall A-101"},
    {"code": "CS502", "subject": "Database Systems", "date": d(7), "time": "14:00", "duration": "3 hrs", "room": "Hall B-204"},
    {"code": "CS503", "subject": "Computer Networks", "date": d(11), "time": "10:00", "duration": "3 hrs", "room": "Hall A-102"},
    {"code": "MA501", "subject": "Probability & Statistics", "date": d(15), "time": "14:00", "duration": "3 hrs", "room": "Hall C-010"},
    {"code": "CS504", "subject": "Software Engineering", "date": d(19), "time": "10:00", "duration": "2 hrs", "room": "Lab 3"},
]

RESULTS = [  # previous semester
    {"code": "CS401", "subject": "Data Structures", "credits": 4, "internal": 38, "external": 52, "attendance": 92},
    {"code": "CS402", "subject": "Algorithms", "credits": 4, "internal": 33, "external": 44, "attendance": 85},
    {"code": "CS403", "subject": "Computer Organization", "credits": 3, "internal": 27, "external": 31, "attendance": 71},
    {"code": "MA401", "subject": "Discrete Mathematics", "credits": 3, "internal": 30, "external": 36, "attendance": 78},
    {"code": "HS401", "subject": "Technical Communication", "credits": 2, "internal": 40, "external": 50, "attendance": 96},
]

EVENTS = [
    {"date": d(1), "title": "Assignment due: DBMS ER diagram", "type": "deadline"},
    {"date": d(2), "title": "OS revision session", "type": "class"},
    {"date": d(9), "title": "Project review - Software Engineering", "type": "class"},
    {"date": d(13), "title": "Fee payment last date", "type": "deadline"},
    {"date": d(22), "title": "Winter break begins", "type": "holiday"},
    {"date": d(-3), "title": "Tech fest", "type": "event"},
]


# ---- Helpers ---------------------------------------------------------------
def grade_for(total):
    for cutoff, grade, pts in [(90, "O", 10), (80, "A+", 9), (70, "A", 8), (60, "B+", 7), (50, "B", 6), (40, "C", 5)]:
        if total >= cutoff:
            return grade, pts
    return "F", 0


def scored_results():
    rows = []
    for r in RESULTS:
        total = r["internal"] + r["external"]
        grade, pts = grade_for(total)
        rows.append({**r, "total": total, "grade": grade, "points": pts})
    return rows


def gpa(rows):
    credits = sum(r["credits"] for r in rows)
    return round(sum(r["points"] * r["credits"] for r in rows) / credits, 2) if credits else 0.0


def upcoming_exams():
    return sorted((e for e in EXAMS if e["date"] >= date.today()), key=lambda e: e["date"])


def build_suggestions():
    rows = scored_results()
    tips = []
    exams = upcoming_exams()
    if exams:
        nxt = exams[0]
        days = (nxt["date"] - date.today()).days
        tips.append({"level": "high" if days <= 5 else "medium", "title": f"{nxt['subject']} is in {days} day(s)",
                     "body": "Finish a full past-paper under timed conditions and list weak topics for a final revision pass."})
    for a, b in zip(exams, exams[1:]):
        if (b["date"] - a["date"]).days <= 3:
            tips.append({"level": "medium", "title": f"Tight gap: {a['subject']} -> {b['subject']}",
                         "body": "Less than 4 days between these exams. Split revision time roughly 40/60 toward the later exam."})
    for r in rows:
        if r["attendance"] < 75:
            tips.append({"level": "high", "title": f"Low attendance in {r['subject']} ({r['attendance']}%)",
                         "body": "Below the usual 75% threshold. Speak to the faculty about eligibility and make-up options."})
        if r["total"] < 60:
            tips.append({"level": "medium", "title": f"Strengthen {r['subject']} fundamentals",
                         "body": f"You scored {r['total']}/100 last semester. Revisit core concepts, as they often carry into advanced courses."})
    tips.append({"level": "low", "title": "Plan study blocks", "body": "Use 90-minute focused blocks with 15-minute breaks, and schedule the hardest subject in your best-focus hours."})
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(tips, key=lambda t: order[t["level"]])


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper


@app.context_processor
def inject_user():
    return {"user": USERS.get(session.get("user")), "today": date.today()}


# ---- Routes ----------------------------------------------------------------
@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("guest"):
            username, password = "guest", "guest"
        else:
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
        u = USERS.get(username)
        if u and u["password"] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    rows = scored_results()
    return render_template("dashboard.html", exams=upcoming_exams()[:3], gpa=gpa(rows),
                           events=sorted((e for e in EVENTS if e["date"] >= date.today()), key=lambda e: e["date"])[:4],
                           tips=build_suggestions()[:3], exam_count=len(upcoming_exams()))


@app.route("/exams")
@login_required
def exams():
    return render_template("exams.html", exams=upcoming_exams())


@app.route("/results")
@login_required
def results():
    rows = scored_results()
    return render_template("results.html", rows=rows, gpa=gpa(rows))


@app.route("/calendar")
@login_required
def calendar_view():
    t = date.today()
    y = request.args.get("y", t.year, type=int)
    m = request.args.get("m", t.month, type=int)
    if not 1 <= m <= 12:
        y, m = t.year, t.month
    items = {}
    for e in EXAMS:
        items.setdefault(e["date"], []).append({"title": f"Exam: {e['subject']}", "type": "exam"})
    for e in EVENTS:
        items.setdefault(e["date"], []).append(e)
    weeks = [[(date(y, m, day) if day else None) for day in wk]
             for wk in pycal.Calendar(firstweekday=6).monthdayscalendar(y, m)]
    py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    return render_template("calendar.html", weeks=weeks, items=items, month_name=pycal.month_name[m],
                           y=y, m=m, prev=(py, pm), nxt=(ny, nm))


@app.route("/suggestions")
@login_required
def suggestions():
    return render_template("suggestions.html", tips=build_suggestions())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
