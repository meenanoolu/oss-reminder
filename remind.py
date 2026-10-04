import argparse, datetime, json, os, re, sys, requests

sys.stdout.reconfigure(encoding="utf-8")   # so the log file and the terminal accept any character

PROGRAMS = ["gsoc", "outreachy"]          # add "lfx", "kde" when their snapshots exist
MILESTONES = (7, 1)                       # days before a date
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
SENT_FILE = "sent.json"

# Events that are about organizations or Google, not about the applicant
SKIP_EVENT_WORDS = ("mentoring organizations can begin", "mentoring organization application",
                    "program administrators review", "org admins")

parser = argparse.ArgumentParser()
parser.add_argument("--today", help="pretend today is YYYY-MM-DD (demo; also uses dates that are already past)")
parser.add_argument("--dry-run", action="store_true", help="print the reminders, send nothing, save nothing")
parser.add_argument("--to", default="me", choices=["me", "friend"], help="whose phone")
args = parser.parse_args()

if args.today and args.to == "friend":
    sys.exit("Demo dates are only sent to yourself. Remove --to friend.")

cfg = json.load(open("config.json"))
if args.to == "friend":
    if not cfg.get("friend_topic"):
        sys.exit('Add "friend_topic" to config.json first')
    topic = cfg["friend_topic"]
else:
    topic = cfg["ntfy_topic"]

today = datetime.date.fromisoformat(args.today) if args.today else datetime.datetime.now(IST).date()
sent = {}
if not args.today and os.path.exists(SENT_FILE):
    sent = json.load(open(SENT_FILE))

def short(text):
    return re.sub(r"\s*\([^)]*\)", "", text).strip()

def event_time_ist(d):
    """The event as an IST datetime. Uses the UTC time from the page when there is one."""
    day = datetime.date.fromisoformat(d["end_date"])
    t = re.search(r"(\d{1,2}):(\d{2})", str(d.get("time_utc") or ""))
    if t:
        try:
            utc = datetime.datetime.combine(
                day, datetime.time(int(t.group(1)), int(t.group(2))), tzinfo=datetime.timezone.utc)
            return utc.astimezone(IST), True
        except ValueError:
            pass
    return datetime.datetime.combine(day, datetime.time(0, 0), tzinfo=IST), False

def push(title, body, link):
    if args.dry_run:
        print("---", title)
        print(body, "\n")
        return
    r = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={"Title": title, "Tags": "alarm_clock",
                 "Actions": f"view, Open official page, {link}"},
    )
    r.raise_for_status()

count = 0
for name in PROGRAMS:
    path = f"data/{name}.json"
    if not os.path.exists(path):
        continue
    data = json.load(open(path, encoding="utf-8"))
    pool = list(data.get("dates", []))
    if args.today:                                   # demo: also look at dates that are now past
        pool += data.get("past_dates", [])
    reviewed = f"reviewed/{name}.json"
    prep_src = json.load(open(reviewed, encoding="utf-8")) if os.path.exists(reviewed) else data
    prepare = [short(p) for p in prep_src.get("prepare", [])][:3]

    for d in pool:
        if any(w in d["event"].lower() for w in SKIP_EVENT_WORDS):
            continue
        when, has_time = event_time_ist(d)
        days_left = (when.date() - today).days
        for m in MILESTONES:
            if not (0 <= days_left <= m):
                continue
            if m == 7 and days_left <= 1:            # the 1-day reminder covers this
                continue
            key = f"{name}|{d['event']}|{d['end_date']}|{m}"
            if key in sent:
                continue
            label = "today" if days_left == 0 else "tomorrow" if days_left == 1 else f"in {days_left} days"
            when_text = f"{when:%Y-%m-%d %H:%M} IST" if has_time else d["end_date"]
            from_text = f" (from {d['start_date']})" if d.get("start_date") and d["start_date"] != d["end_date"] else ""
            body = f"{d['event']}: {when_text}{from_text}"
            if prepare:
                body += "\n\nHave ready:\n" + "\n".join(f"- {p}" for p in prepare)
            body += f"\n\nFrom the official page, as of {data['snapshot_date']}. Dates can change, so double-check."
            title = ("DEMO " if args.today else "") + f"{name.upper()} reminder: {label}"
            push(title, body, data["sources"][0])
            sent[key] = datetime.datetime.now(IST).isoformat(timespec="seconds")
            count += 1

if not args.today and not args.dry_run:
    json.dump(sent, open(SENT_FILE, "w"), indent=2)
print(f"{count} reminder(s) {'printed' if args.dry_run else 'sent'} for {today}")