import json, sys, re, requests

def short(text):
    # remove "(...)" asides only; keeps the full meaning of each rule
    return re.sub(r"\s*\([^)]*\)", "", text).strip()

def as_sentence(text):
    # grammar fix done by code, not by the model
    t = short(text).replace("You can apply if you ", "").strip().rstrip(".")
    t = re.sub(r"^be ", "are ", t)
    t = t.replace(" they ", " you ").replace(" their ", " your ")
    return t

def as_cannot(text):
    t = short(text).replace("You cannot apply if ", "", 1).strip().rstrip(".")
    if t.startswith("otherwise prohibited"):
        t = "you are " + t
    return t

name = sys.argv[1]                      # e.g. gsoc
data = json.load(open(f"data/{name}.json", encoding="utf-8"))
topic = json.load(open("config.json"))["ntfy_topic"]
TITLE = name.upper()

# lines that are about organizations/Google, not about the applicant
ORG_WORDS = ("Org Applications", "Organization applications", "reviews all",
             "Org Admins", "Org requests")

def send(title, body, link=None, tags=None):
    headers = {"Title": title}          # keep titles plain text (no emoji)
    if link:
        # button on the notification and in the app; tapping the notification itself opens the app
        headers["Actions"] = f"view, Open official page, {link}"
    if tags:
        headers["Tags"] = tags
    r = requests.post(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), headers=headers)
    r.raise_for_status()

footer = f"\n\nAs of {data['snapshot_date']}. Always double-check on the official page."

# Message 1: dates (dates_for_approved_applicants are never sent as reminders)
if data["dates"]:
    lines = [f"- {d['event']}: {d['start_date']} to {d['end_date']}" for d in data["dates"]]
    body1 = "Upcoming dates:\n" + "\n".join(lines)
else:
    timing = [t for t in data["typical_timing"] if not any(w in t for w in ORG_WORDS)]
    head = ("The current round is CLOSED to new applicants. The next round is NOT announced yet. I'll tell you as soon as it appears."
            if data.get("applications_closed")
            else "Next dates are NOT announced yet. I'll tell you as soon as they appear.")
    body1 = head + "\n\nUsually:\n" + "\n".join(f"- {short(t)}" for t in timing)
send(f"{TITLE}: dates", body1 + footer, link=data["sources"][0], tags="calendar")

# Message 2: can you apply, and what to prepare
can = [as_sentence(e) for e in data["eligibility"]]
cannot = [as_cannot(c) for c in data["cannot_apply_if"]]
body2 = ("You can apply if you:\n" + "\n".join(f"- {c}" for c in can) +
         "\n\nTo apply:\n" + "\n".join(f"- {short(p)}" for p in data["prepare"]) +
         "\n\nYou cannot apply if:\n" + "\n".join(f"- {c}" for c in cannot) +
         "\n\nOpen this message in the ntfy app to read it all.")
send(f"{TITLE}: can you apply?", body2 + footer, link=data["sources"][-1], tags="white_check_mark")
print("sent 2 messages")