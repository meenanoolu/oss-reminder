import json, re, sys, datetime, ollama

MODEL = "gemma3:4b"
TODAY = datetime.date.today()
OPTIONS = {"num_ctx": 8192, "temperature": 0}
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
CLOSED_PHRASES = ("initial applications are closed", "no longer accepting initial applications")
TABLE_ROWS = ("Initial applications open", "Initial applications due",
              "Contribution period opens", "Contribution period ends", "Interns announced")

# A line that starts like a date, e.g. "March 16 - 18:00 UTC" or "Aug. 24, 2026 at 4pm UTC"
DATE_LINE = re.compile(
    r"^[ \t]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?[ \t]+\d{1,2}", re.M)

# Base prompt = the exact v6 prompt (found 9 of 9 GSoC dates). Do not edit it for one program.
DATES_PROMPT = """Extract every dated event from the timeline text below.
Return JSON: {"dates": [{"event": str, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "time_utc": "HH:MM" or null}]}
Rules:
- Copy the event wording from the text. Do not invent events and do not skip any.
- A single day has the same start_date and end_date.
- For a range like "August 24 - 31" the end is August 31. For "August 24 - November 2" the end is November 2.
- Use the year in the page heading.
- Ignore the general month-by-month timing section (it has no exact dates).
- Only include events that matter to an applicant BEFORE being selected: accepted organizations published, discussing ideas with organizations, applications opening and closing, and results announced. Skip organization and mentor steps, and everything after results are announced (bonding, coding, evaluations, final submissions).<<EXTRA>>

TEXT:
"""

# Rules that only one program needs go here, so they cannot break the others
EXTRA_DATE_RULES = {
    "outreachy": (
        '\n- Use the year written next to each date.'
        '\n- Convert times like "4pm UTC" to 24-hour HH:MM ("16:00"). Use null if no time is given.'
        '\n- For "Oct. 5, 2026 to Nov. 2, 2026" the start is 2026-10-05 and the end is 2026-11-02.'
    ),
}
JOIN_WRAPPED_LINES = {"outreachy"}   # programs whose pasted dates wrap onto a second line

INFO_PROMPT = """Using ONLY the text below, return JSON:
{"eligibility": [str], "cannot_apply_if": [str], "prepare": [str]}
- eligibility: what an applicant MUST be or have (age, student status, work eligibility, and so on). Write each as a positive requirement.
- cannot_apply_if: situations that stop someone from applying. Write each starting with "You cannot apply if". Ignore organization and mentor rules, and ignore general descriptions of the program.
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

def tidy(text):
    # join lines that were wrapped, like "Nov. 2, 2026" / "at 4pm UTC"
    return re.sub(r"\n(?=at \d|to )", " ", text)

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

name = sys.argv[1]
text = open(f"snapshots/{name}.txt", encoding="utf-8").read()
blocks = re.findall(
    r"^SOURCE:\s*(\S+)\s*\|\s*(\w+)\s*\n(.*?)(?=^SOURCE:|\Z)", text, flags=re.M | re.S
)
if not blocks:
    sys.exit("No blocks found. Each source must start with: SOURCE: <url> | dates   (or | timing, | rules)")

dates_prompt = DATES_PROMPT.replace("<<EXTRA>>", EXTRA_DATE_RULES.get(name, ""))

result = {"program": name, "dates": [], "eligibility": [], "cannot_apply_if": [], "prepare": [], "typical_timing": []}
all_dates = []

for url, kind, body in blocks:
    body = body[:9000]
    if kind == "dates":
        if name in JOIN_WRAPPED_LINES:
            body = tidy(body)
        # Safety net: the model never sees the post-selection dates
        before_selection = body.split("Community Bonding Period")[0]
        found = ask(dates_prompt, before_selection).get("dates", [])
        all_dates += found
        # Cross-check by plain code: a page full of date lines should not give an empty answer
        date_lines = len(DATE_LINE.findall(before_selection))
        if date_lines and len(found) < date_lines * 0.7:
            print(f"WARNING ({name}): page has about {date_lines} date lines but the model returned {len(found)}. Check by hand.")
    if kind in ("dates", "timing"):
        result["typical_timing"] += typical_timing(body)
    if kind == "rules":
        info = ask(INFO_PROMPT, body)
        for key in ("eligibility", "cannot_apply_if", "prepare"):
            for item in info.get(key, []):
                if item not in result[key]:
                    result[key].append(item)

# Filtering is done by code, not by the model
upcoming = []
for d in all_dates:
    end = to_date(d.get("end_date"))
    if end is None:
        print("WARNING: unreadable date, check by hand:", d)
    elif end >= TODAY:
        upcoming.append(d)

# If the page itself says applications are closed, remaining dates are only for approved applicants
if any(p in text.lower() for p in CLOSED_PHRASES):
    result["applications_closed"] = True
    result["dates_for_approved_applicants"] = upcoming
    result["note"] = "The current round is closed to new applicants. Any dates listed are only for people already approved."
else:
    result["dates"] = upcoming
    if not upcoming:
        result["note"] = "No upcoming application dates found on the page (next season may not be announced yet)."

# These come from code, not from the AI, so they can't be made up
result["sources"] = list(dict.fromkeys(b[0] for b in blocks))
result["snapshot_date"] = TODAY.isoformat()
result["total_dates_found"] = len(all_dates)

with open(f"data/{name}.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(json.dumps(result, indent=2, ensure_ascii=False))