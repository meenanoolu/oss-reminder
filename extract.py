import json, re, sys, datetime, ollama

MODEL = "gemma3:4b"
TODAY = datetime.date.today()
OPTIONS = {"num_ctx": 8192, "temperature": 0}
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
MONTH_NUM = {m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)}
CLOSED_PHRASES = ("initial applications are closed", "no longer accepting initial applications")
TABLE_ROWS = ("Initial applications open", "Initial applications due",
              "Contribution period opens", "Contribution period ends", "Interns announced")

CODE_DATE_PARSERS = {"outreachy"}        # clean date tables: plain code reads them, not the model
CHUNK_RULES_BY_HEADING = set()           # empty on purpose: chunking made results worse (see NOTES v8)

# A line that starts like a date, e.g. "March 16 - 18:00 UTC" or "Aug. 24, 2026 at 4pm UTC"
DATE_LINE = re.compile(
    r"^[ \t]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[ \t]+\d{1,2}", re.M)
DATE_IN_TEXT = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s+(\d{4})")

# This is the exact v6 prompt (found 9 of 9 GSoC dates). Do not edit it for one program.
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
{"eligibility": [str], "cannot_apply_if": [str], "prepare": [str]}
- eligibility: what an applicant MUST be or have (age, student status, work eligibility, and so on). Write each as a positive requirement.
- cannot_apply_if: situations that stop someone from applying. Write each starting with "You cannot apply if". Ignore organization and mentor rules, and ignore general descriptions of the program.
- prepare: what an applicant must do or submit in order to APPLY. Do not include anything that happens after being accepted.
Never guess. Use an empty list if the text has nothing for a key.
Write short, simple points for a beginner.

TEXT:
"""

PREP_PROMPT = """Using ONLY the text below, return JSON: {"prepare": [str]}
- prepare: what an applicant must have ready, or must do or avoid, when filling in the application (documents to collect, limits on essays, rules about how to write them).
Never guess. Write short, simple points for a beginner.

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

def tidy(text):
    # join lines that were wrapped, like "Nov. 2, 2026" / "at 4pm UTC"
    return re.sub(r"\n(?=at \d|to )", " ", text)

def parse_table_dates(body):
    """Plain code, no AI: rows like 'Aug. 24, 2026 at 4pm UTC <tab> Initial applications open'."""
    rows = []
    for line in tidy(body).splitlines():
        parts = [p.strip() for p in re.split(r"\t+|\s{2,}", line.strip()) if p.strip()]
        if len(parts) != 2:
            continue
        when, event = parts
        found = DATE_IN_TEXT.findall(when)
        if not found or "internships period" in event.lower():
            continue
        try:
            iso = [datetime.date(int(y), MONTH_NUM[m[:3].lower()], int(d)).isoformat()
                   for m, d, y in found]
        except (KeyError, ValueError):
            print("WARNING: unreadable date row, check by hand:", line)
            continue
        t = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s+UTC", when, re.I)
        time_utc = None
        if t:
            hour = int(t.group(1)) % 12 + (12 if t.group(3).lower() == "pm" else 0)
            time_utc = f"{hour:02d}:{t.group(2) or '00'}"
        rows.append({"event": event, "start_date": iso[0], "end_date": iso[-1], "time_utc": time_utc})
    return rows

def typical_timing(body):
    """Plain code, no AI."""
    out = []
    # GSoC style: month headings with lines under them
    if "General Timing" in body:
        section = body.split("General Timing", 1)[1]
        month = None
        for line in section.splitlines():
            line = line.strip()
            if line in MONTHS:
                month = line
            elif month and line:
                if line.lower().startswith("community bonding"):
                    break  # everything after this is post-selection
                out.append(f"{month}: {line}")
    # Outreachy style: a table with one column per round
    if "Important Round Dates" in body:
        for line in body.splitlines():
            parts = [p.strip() for p in re.split(r"\t+|\s{2,}", line.strip()) if p.strip()]
            if len(parts) == 3 and parts[0] in TABLE_ROWS:
                out.append(f"{parts[0]}: {parts[1]} for the May-Aug round, {parts[2]} for the Dec-Mar round")
    return out

def clean_up(result):
    """Plain code: move 'Must not ...' lines out of eligibility, then remove duplicates."""
    keep = []
    for e in result["eligibility"]:
        m = re.match(r"^(?:you\s+)?must not (be|have)\s+(.*)$", e.strip(), re.I)
        if m:
            verb = "are" if m.group(1).lower() == "be" else "have"
            result["cannot_apply_if"].append(f"You cannot apply if you {verb} {m.group(2).rstrip('.')}")
        else:
            keep.append(e)
    result["eligibility"] = keep
    seen, unique = set(), []
    for c in result["cannot_apply_if"]:
        key = re.sub(r"[^a-z0-9 ]", "", c.lower())
        if key not in seen:
            seen.add(key)
            unique.append(c)
    result["cannot_apply_if"] = unique

name = sys.argv[1]
text = open(f"snapshots/{name}.txt", encoding="utf-8").read()
blocks = re.findall(
    r"^SOURCE:\s*(\S+)\s*\|\s*(\w+)\s*\n(.*?)(?=^SOURCE:|\Z)", text, flags=re.M | re.S
)
if not blocks:
    sys.exit("No blocks found. Each source must start with: SOURCE: <url> | dates   (or | timing, | rules, | prep)")

result = {"program": name, "dates": [], "eligibility": [], "cannot_apply_if": [], "prepare": [], "typical_timing": []}
all_dates = []

for url, kind, body in blocks:
    body = body[:9000]
    if kind == "dates":
        if name in CODE_DATE_PARSERS:
            scanned = body
            found = parse_table_dates(body)
        else:
            # Safety net: the model never sees the post-selection dates
            scanned = body.split("Community Bonding Period")[0]
            found = ask(DATES_PROMPT, scanned).get("dates", [])
        all_dates += found
        # Cross-check by plain code: a page full of date lines should not give an empty answer
        date_lines = len(DATE_LINE.findall(scanned))
        if date_lines and len(found) < date_lines * 0.7:
            print(f"WARNING ({name}): page has about {date_lines} date lines but {len(found)} were found. Check by hand.")
    if kind in ("dates", "timing"):
        result["typical_timing"] += typical_timing(body)
    if kind == "rules":
        chunks = re.split(r"(?m)^(?=\d\. )", body) if name in CHUNK_RULES_BY_HEADING else [body]
        for chunk in chunks:
            if not chunk.strip():
                continue
            info = ask(INFO_PROMPT, chunk)
            for key in ("eligibility", "cannot_apply_if", "prepare"):
                for item in info.get(key, []):
                    if item not in result[key]:
                        result[key].append(item)
    if kind == "prep":
        for item in ask(PREP_PROMPT, body).get("prepare", []):
            if item not in result["prepare"]:
                result["prepare"].append(item)

clean_up(result)

# Filtering is done by code, not by the model
upcoming, past = [], []
for d in all_dates:
    end = to_date(d.get("end_date"))
    if end is None:
        print("WARNING: unreadable date, check by hand:", d)
    elif end >= TODAY:
        upcoming.append(d)
    else:
        past.append(d)

# If the page itself says applications are closed, remaining dates are only for approved applicants
if any(p in text.lower() for p in CLOSED_PHRASES):
    result["applications_closed"] = True
    result["dates_for_approved_applicants"] = upcoming
    result["note"] = "The current round is closed to new applicants. Any dates listed are only for people already approved."
else:
    result["dates"] = upcoming
    if not upcoming:
        result["note"] = "No upcoming application dates found on the page (next season may not be announced yet)."

result["past_dates"] = past   # only used by remind.py --today (the demo)

# These come from code, not from the AI, so they can't be made up
result["sources"] = list(dict.fromkeys(b[0] for b in blocks))
result["snapshot_date"] = TODAY.isoformat()
result["total_dates_found"] = len(all_dates)

with open(f"data/{name}.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(json.dumps(result, indent=2, ensure_ascii=False))