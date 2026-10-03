import json, re, sys, datetime, ollama

MODEL = "gemma3:4b"
TODAY = datetime.date.today().isoformat()

PROMPT = """You help beginners apply to open-source programs.
Using ONLY the page text below, return JSON with exactly these keys:
{
 "program": str,
 "dates": [{"event": str, "date": "YYYY-MM-DD" or null, "timezone": str or null}],
 "typical_timing": [str],
 "eligibility": [str],
 "prepare": [str],
 "start_here": [str]
}
Rules:
- Never guess. If something is not stated, use null or an empty list.
- Today's date is TODAY. Only put dates in "dates" that are today or later.
- Approximate month-level patterns (like a "General Timing" section) go in "typical_timing", never in "dates".
- "eligibility" is what a CONTRIBUTOR/applicant must meet. Ignore organization and mentor rules.
- "prepare" is what the applicant must do or submit to apply.
- Write all lists as short, simple points for a beginner.

PAGE TEXT:
""".replace("TODAY", TODAY)

name = sys.argv[1]
text = open(f"snapshots/{name}.txt", encoding="utf-8").read()[:15000]

reply = ollama.chat(
    model=MODEL,
    messages=[{"role": "user", "content": PROMPT + text}],
    format="json",
    options={"num_ctx": 8192, "temperature": 0},
)
data = json.loads(reply["message"]["content"])

# These two come from code, not from the AI, so they can't be made up
data["sources"] = re.findall(r"^SOURCE:\s*(\S+)", text, flags=re.M)
data["snapshot_date"] = TODAY

with open(f"data/{name}.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(json.dumps(data, indent=2, ensure_ascii=False))