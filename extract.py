import json, re, sys, datetime, ollama

MODEL = "gemma3:4b"
TODAY = datetime.date.today()
OPTIONS = {"num_ctx": 8192, "temperature": 0}
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

DATES_PROMPT = """Extract every dated event from the timeline text below.
Return JSON: {"dates": [{"event": str, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "time_utc": "HH:MM" or null}]}
Rules:
- Copy the event wording from the text. Do not invent events and do not skip any.
- A single day has the same start_date and end_date.
- For a range like "August 24 - 31" the end is August 31. For "August 24 - November 2" the end is November 2.
- Use the year in the page heading.
- Ignore the general month-by-month timing section (it has no exact dates).
- Only include events that matter to an applicant BEFORE being selected: accepted organizations published, discussing ideas with organizations, applications opening and closing, and results announced. Skip organization and mentor steps, and everything after results are announced (bonding, coding, evaluations, final submissions).

TEXT:
"""

INFO_PROMPT = """Using ONLY the text below, return JSON:
{"eligibility": [str], "prepare": [str]}
- eligibility: every formal requirement AND every disqualifier for an applicant (age, student status, country, past participation, and so on). Ignore organization and mentor rules, and ignore general descriptions of the program.
- prepare: what an applicant must do or submit in order to APPLY. Do not include anything that happens after being accepted.
Never guess. Use an empty list if the text has nothing for a key.
Write short, simple points for a beginner.

TEXT:
"""

def ask(prompt, text):
    reply = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt + text}],
        format="json",
        options=OPTIONS,
    )
    return json.loads(reply["message"]["content"])

def to_date(s):
    try:
        return datetime.date.fromisoformat(str(s))
    except ValueError:
        return None

def typical_timing(body):
    """Plain code, no AI: turn the 'General Timing' month list into 'Month: event' lines."""
    if "General Timing" not in body:
        return []
    section = body.split("General Timing", 1)[1]
    out, month = [], None
    for line in section.splitlines():
        line = line.strip()
        if line in MONTHS:
            month = line
        elif month and line:
            if line.lower().startswith("community bonding"):
                break  # everything after this is post-selection
            out.append(f"{month}: {line}")
    return out

name = sys.argv[1]
text = open(f"snapshots/{name}.txt", encoding="utf-8").read()
blocks = re.findall(
    r"^SOURCE:\s*(\S+)\s*\|\s*(\w+)\s*\n(.*?)(?=^SOURCE:|\Z)", text, flags=re.M | re.S
)
if not blocks:
    sys.exit("No blocks found. Each source must start with: SOURCE: <url> | dates   (or | rules)")

result = {"program": name, "dates": [], "eligibility": [], "prepare": [], "typical_timing": []}
all_dates = []

for url, kind, body in blocks:
    body = body[:9000]
    if kind == "dates":
        # Safety net: the model never sees the post-selection dates
        before_selection = body.split("Community Bonding Period")[0]
        all_dates += ask(DATES_PROMPT, before_selection).get("dates", [])
        result["typical_timing"] += typical_timing(body)
    if kind == "rules":
        info = ask(INFO_PROMPT, body)
        for key in ("eligibility", "prepare"):
            for item in info.get(key, []):
                if item not in result[key]:
                    result[key].append(item)

# Filtering is done by code, not by the model
for d in all_dates:
    end = to_date(d.get("end_date"))
    if end is None:
        print("WARNING: unreadable date, check by hand:", d)
    elif end >= TODAY:
        result["dates"].append(d)

if not result["dates"]:
    result["note"] = "No upcoming application dates found on the page (next season may not be announced yet)."

# These come from code, not from the AI, so they can't be made up
result["sources"] = [b[0] for b in blocks]
result["snapshot_date"] = TODAY.isoformat()
result["total_dates_found"] = len(all_dates)

with open(f"data/{name}.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(json.dumps(result, indent=2, ensure_ascii=False))