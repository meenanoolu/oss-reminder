# oss-reminder

Never miss an open-source program deadline again, and know what to prepare before it arrives.

I built this for a friend who wants to start contributing to open source. Every program (GSoC, Outreachy, ...) keeps its dates and rules on different pages. The emails get lost in spam, and a missed deadline means waiting six months to a year. oss-reminder reads the official pages with a **local open-weight model (Gemma 3 4B through Ollama)**, keeps the dates and rules in one place, and sends push reminders **7 days and 1 day before** each date, at the time of day you choose.

Built for the DEV Hacktoberfest 2026 Weekend Challenge: *Build for a Friend*.

## What lands on her phone
- **Dates:** the open application dates, or an honest "next round not announced yet" with the usual month pattern.
- **Can you apply?** who can apply, who cannot, and what to prepare (documents, essays, limits).
- **Reminders:** a countdown message 7 days and 1 day before each date, with a "Have ready" list.
- Every message shows the **snapshot date** and an **Open official page** button, so she can always check the source.

## How it works
```
saved page text --> extract.py (Gemma 3 4B, local) --> data/<program>.json
                       plain code: date filter, month patterns, cross-checks

reviewed/<program>.json (optional, checked by hand) --+
                                                      +--> notify.py --> phone (ntfy)
data/<program>.json ----------------------------------+

data/<program>.json --> remind.py (daily; 7 and 1 days before) --> phone (ntfy)
```

| Job | Done by |
|---|---|
| Reading messy page text into eligibility, disqualifiers and what to prepare | Gemma 3 4B (local, temperature 0) |
| Date maths, "is this date in the future?", UTC to IST, month patterns, duplicate removal, message wording | plain Python |
| Rules the model got wrong (Outreachy) | checked by hand (`reviewed/`) |

The model only reads. Code decides what counts as upcoming, so the model cannot invent a deadline that then triggers a reminder.

## Setup
You need Python 3.10+ and [Ollama](https://ollama.com).

```bash
git clone https://github.com/meenanoolu/oss-reminder
cd oss-reminder
python -m venv venv
venv\Scripts\activate          # Windows. On Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
ollama pull gemma3:4b
```

### 1. Choose a private ntfy topic
Install the [ntfy](https://ntfy.sh) app on the phone and subscribe to a hard-to-guess topic. Topics on the public server have no password, so the name is the secret.
```bash
python -c "import secrets; print('oss-' + secrets.token_hex(8))"
```
Copy `config.example.json` to `config.json` and put your topic in it. `config.json` is git-ignored.
```json
{"ntfy_topic": "oss-your-random-name-here"}
```
To send to a second phone, add `"friend_topic": "..."` and use `remind.py --to friend`.

### 2. Save the official pages as snapshots
`snapshots/` is git-ignored, because it holds text copied from other sites. For each program, copy the text of its official pages into `snapshots/<program>.txt`, one block per page:
```
SOURCE: https://example.org/timeline | dates
(page text)

SOURCE: https://example.org/rules | rules
(page text)
```
Block kinds: `dates` (a timeline), `timing` (a "usual month pattern" table), `rules` (eligibility), `prep` (what to have ready when applying).

### 3. Extract, then notify
```bash
python extract.py gsoc          # reads snapshots/gsoc.txt, writes data/gsoc.json
python notify.py gsoc           # sends the summary to your phone
```
`extract.py` prints a WARNING when a page has many date lines but few were found, so an empty result never passes silently.

### 4. Reminders
```bash
python remind.py --dry-run                       # print what would be sent today, send nothing
python remind.py --today 2026-03-24 --dry-run    # demo: pretend it is a week before GSoC 2026's deadline
python remind.py --today 2026-03-24              # send the demo reminder to your own phone
python remind.py                                 # real run (sends nothing when no dates are open)
```
Run it daily. The time of day is the schedule you choose. On Windows:
```bash
schtasks /create /tn "OSS Reminder" /sc daily /st 17:30 /tr "cmd /c cd /d C:\path\to\oss-reminder && venv\Scripts\python.exe remind.py >> reminder.log 2>&1"
```
Change `/st 17:30` to move the reminders to another hour. On Linux or macOS use cron (not tested). Reminders are counted in IST. `sent.json` keeps a reminder from going out twice, and if the computer was off on day 7, a catch-up reminder goes out the next time it runs.

## Hand-reviewed rules
A 4B model is good at reading, but it dropped and garbled rules. For Outreachy I check the rules myself and keep them in `reviewed/outreachy.json`. When that file exists, `notify.py` uses it and the message says "Rules checked by hand on <date>". The raw model output stays in `data/`, so the accuracy numbers stay honest.

## How accurate was the model?
Full write-up with every version: [NOTES.md](NOTES.md). Short version, checked line by line against the official pages:

| Program | What I checked | Result |
|---|---|---|
| GSoC v1 (one prompt) | 18 dates | 14 correct, 1 half-right, 3 wrong, 1 missing |
| GSoC v1 | contributor rules | 4 of 6 found; the embargo rule and the "2+ times before" rule were missing |
| GSoC v4 and later | 10 rules | 9 found, 0 flipped. The "not" that flipped a disqualifier in v3 is fixed |
| Outreachy | 16 rules | 11 correct, 1 garbled, 4 missing, so the rules are hand-reviewed |

## Limits
- Only **GSoC** and **Outreachy** so far. LFX Mentorship and Season of KDE are not done yet.
- Dates change only when I refresh the snapshots by hand. There is no "dates changed" alert yet.
- The computer must be on and awake at reminder time. Hosting the scheduler on an always-on machine is the real fix.
- Right now neither program has open application dates, so a real run sends nothing. The demo uses a simulated date and its titles start with "DEMO".
- Only the notification text leaves the machine. It goes through ntfy.sh, which is open source and can be self-hosted. Topic names are secret by obscurity only.
- Rules and dates change every season. Always check the official page.

## Files
| File | What it does |
|---|---|
| `extract.py` | Gemma reads the snapshots into `data/<program>.json` |
| `notify.py` | sends the summary messages |
| `remind.py` | sends the 7-day and 1-day reminders |
| `reviewed/` | rules checked by hand |
| `NOTES.md` | every version, what broke, and what I learned |
| `config.example.json` | the config format |

## License
MIT. Built with Claude as a coding assistant. I ran and checked everything myself.