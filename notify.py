import json, sys, requests
import re

def short(text):
    # remove "(...)" asides only; keeps the full meaning of each rule
    return re.sub(r"\s*\([^)]*\)", "", text).strip()

name = sys.argv[1]                      # e.g. gsoc
data = json.load(open(f"data/{name}.json", encoding="utf-8"))
topic = json.load(open("config.json"))["ntfy_topic"]
TITLE = name.upper()

# lines that are about organizations/Google, not about the applicant
ORG_WORDS = ("Org Applications", "Organization applications", "reviews all",
             "Org Admins", "Org requests")

def send(title, body, click=None, tags=None):
    headers = {"Title": title}          # keep titles plain text (no emoji)
    if click:
        headers["Click"] = click
    if tags:
        headers["Tags"] = tags
    r = requests.post(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"), headers=headers)
    r.raise_for_status()

footer = f"\n\nAs of {data['snapshot_date']}. Always double-check on the official page."
link = data["sources"][0]

# Message 1: dates
if data["dates"]:
    lines = [f"- {d['event']}: {d['start_date']} to {d['end_date']}" for d in data["dates"]]
    body1 = "Upcoming dates:\n" + "\n".join(lines)
else:
    timing = [t for t in data["typical_timing"] if not any(w in t for w in ORG_WORDS)]
    body1 = ("Next dates are NOT announced yet. I'll tell you as soon as they appear.\n\n"
             "Usually:\n" + "\n".join(f"- {t}" for t in timing))
send(f"{TITLE}: dates", body1 + footer, click=link, tags="calendar")

# Message 2: can you apply, and what to prepare
body2 = ("You can apply if you:\n" + "\n".join(f"- {short(e)}" for e in data["eligibility"]) +
         "\n\nTo apply:\n" + "\n".join(f"- {short(p)}" for p in data["prepare"]) +
         "\n\nYou cannot apply if:\n" +
         "\n".join(f"- {short(c.replace('You cannot apply if ', ''))}" for c in data["cannot_apply_if"]) +
         "\n\nTap to open the official rules.")
send(f"{TITLE}: can you apply?", body2 + footer, click=data["sources"][-1], tags="white_check_mark")
print("sent 2 messages")