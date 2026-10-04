import json, os, sys, re, time, requests

MAX_BYTES = 900   # the phone cut a longer message, so each message stays about as short as the dates one

def short(text):
    # remove "(...)" asides only; keeps the full meaning of each rule.
    # asides that mention "hours" are kept, e.g. "(30 hours per week)"
    return re.sub(r"\s*\((?![^)]*\bhours\b)[^)]*\)", "", text).strip()

def as_sentence(text):
    # grammar fix done by code, not by the model
    t = short(text).replace("You can apply if you ", "").strip().rstrip(".")
    t = re.sub(r"^must be ", "be ", t, flags=re.I)
    t = re.sub(r"^must have ", "have ", t, flags=re.I)
    t = re.sub(r"^your visa must allow you to ", "have a visa that allows you to ", t, flags=re.I)
    t = re.sub(r"^be ", "are ", t)
    t = t.replace(" they ", " you ").replace(" their ", " your ")
    return t

def as_cannot(text):
    t = short(text).replace("You cannot apply if ", "", 1).strip().rstrip(".")
    if t.startswith("otherwise prohibited"):
        t = "you are " + t
    return t

def nbytes(s):
    return len(s.encode("utf-8"))

def pack(parts, limit):
    """Group whole sections into messages under the limit. A section that is too long is split by line."""
    pieces = []
    for part in parts:
        if nbytes(part) <= limit:
            pieces.append(part)
        else:
            cur = ""
            for line in part.split("\n"):
                trial = cur + "\n" + line if cur else line
                if cur and nbytes(trial) > limit:
                    pieces.append(cur)
                    cur = line
                else:
                    cur = trial
            if cur:
                pieces.append(cur)
    messages, cur = [], ""
    for p in pieces:
        trial = cur + "\n\n" + p if cur else p
        if cur and nbytes(trial) > limit:
            messages.append(cur)
            cur = p
        else:
            cur = trial
    if cur:
        messages.append(cur)
    return messages

name = sys.argv[1]                      # e.g. gsoc
# a file I checked by hand against the official pages wins over the raw model output
reviewed_path = f"reviewed/{name}.json"
path = reviewed_path if os.path.exists(reviewed_path) else f"data/{name}.json"
data = json.load(open(path, encoding="utf-8"))
print("using", path)
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

base_footer = f"As of {data['snapshot_date']}. Always double-check on the official page."
hand = ""
if path == reviewed_path and data.get("reviewed_on"):
    hand = f"Rules checked by hand on {data['reviewed_on']}. "
rules_footer = "\n\n" + hand + base_footer

outbox = []   # (title, body, link, tags) in reading order

# Message: dates (dates_for_approved_applicants are never sent as reminders)
if data["dates"]:
    lines = [f"- {d['event']}: {d['start_date']} to {d['end_date']}" for d in data["dates"]]
    body1 = "Upcoming dates:\n" + "\n".join(lines)
else:
    timing = [t for t in data["typical_timing"] if not any(w in t for w in ORG_WORDS)]
    head = ("The current round is CLOSED to new applicants. The next round is NOT announced yet. I'll tell you as soon as it appears."
            if data.get("applications_closed")
            else "Next dates are NOT announced yet. I'll tell you as soon as they appear.")
    body1 = head + "\n\nUsually:\n" + "\n".join(f"- {short(t)}" for t in timing)
outbox.append((f"{TITLE}: dates", body1 + "\n\n" + base_footer, data["sources"][0], "calendar"))

# Messages: can you apply, what to prepare. "Good to know" sits next to "can apply"
# because it holds the cohort rules
can_part = "You can apply if you:\n" + "\n".join(f"- {as_sentence(e)}" for e in data["eligibility"])
good = data.get("good_to_know", [])
good_part = ("Good to know:\n" + "\n".join(f"- {g}" for g in good)) if good else ""
prep_part = "To apply:\n" + "\n".join(f"- {short(p)}" for p in data["prepare"])
cannot_part = "You cannot apply if:\n" + "\n".join(f"- {as_cannot(c)}" for c in data["cannot_apply_if"])
parts = [p for p in (can_part, good_part, prep_part, cannot_part) if p]

chunks = pack(parts, MAX_BYTES - nbytes(rules_footer))
for i, body in enumerate(chunks, 1):
    title = f"{TITLE}: can you apply?" + (f" ({i}/{len(chunks)})" if len(chunks) > 1 else "")
    if i == len(chunks):
        body += rules_footer
    outbox.append((title, body, data["sources"][-1], "white_check_mark"))

for title, body, link, tags in outbox:
    print(f"{title}: {nbytes(body)} bytes")

# Newest shows on top in the app, so send in reverse (with a pause) to read top to bottom
for title, body, link, tags in reversed(outbox):
    send(title, body, link=link, tags=tags)
    time.sleep(1.1)
print(f"sent {len(outbox)} messages")