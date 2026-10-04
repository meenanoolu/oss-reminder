# Build notes

Goal: help a friend (beginner in open source) not miss GSoC / Outreachy / LFX / KDE dates,
and know what to prepare. Gemma 3 4B runs locally through Ollama and reads saved page text.
Plain code does the date filtering and the final alerts.

## How I score each version
I compare the model output line by line with the official page text I saved.
Wrong = false or flipped. Missing = a real rule/date left out.
The GSoC contributor rules page has 10 rules: 4 requirements and 6 disqualifiers.

## v1: one prompt for everything
- Dates: 14/18 correct, 1 half-right, 3 wrong, 1 missing
- The wrong dates were all near the end of the list (final evaluations, extended coding)
- Ignored my "only future dates" rule: 16 of 18 dates were already past
- Eligibility: 4 of 6 points found, missed the embargo rule and the "2+ times before" rule
- "start_here" was just link text from the page, not real advice
- Lesson: don't ask a small model to filter dates or do too many jobs at once

## v2: separate prompts, code-side date filter
- dates: correctly empty (Gemma found 9 pre-selection dates, code filtered all of them out)
- eligibility: all rules found, but 3 extra lines came from the timeline page's intro text,
  and one was WRONG: "Applicants must be students" (the rules say "a student OR a beginner")
- prepare: 2 right, 1 wrong stage ("submit final work product" happens after selection)
- typical_timing: BAD. Gemma copied exact 2026 dates (including post-selection ones)
  instead of the month-level pattern, and added "Not specified" lines
- Lesson: I ran the "info" prompt on every page, so marketing text and dates leaked in.
  Reformatting a list is a job plain code does better than the model

## v3: eligibility only from rules pages, typical_timing built by code
- dates: correctly empty
- typical_timing: correct, built by plain Python (no AI). A few org-side lines remain
- prepare: 2/2 correct
- eligibility: all rules present, but 1 had a FLIPPED meaning:
  "have previously participated ... two or more times" is a disqualifier in the rules,
  the model dropped the "not". Dangerous: a beginner could read it as a requirement
- Lesson: small models can lose negation when requirements and disqualifiers share one list

## v4: split requirements from disqualifiers
- Two lists: eligibility (what you must be) and cannot_apply_if (each starts "You cannot apply if")
- Result: 9 of 10 rules found, 0 flipped. The flipped rule is fixed
- New omission: "not be an Organization Administrator or Mentor" was dropped (v3 had it).
  Low impact for a beginner, but still a gap
- Also not listed: the rule allowing up to 3 proposals (nice-to-have)
- Decision: stop tuning GSoC here. An omission is less dangerous than a flip,
  and every message links the official rules page so my friend can double-check

## Notifications (ntfy)
- Sends 2 push messages per program: "dates" and "can you apply?"
- When no dates are announced, the message says so and shows the usual month pattern
- Topic name is private (config.json is in .gitignore). Public ntfy topics have no password,
  so a guessable name would let strangers read/send to it

## Notifications: first real test on my phone
- ntfy works end to end. Android cuts long messages in the notification shade
- Reordered so "To apply" comes before the long "cannot apply" list
- Removed "(...)" asides with plain code instead of truncating, because cutting at a length
  could remove "two or more times" and flip a rule again
- Screenshots saved for the post (before and after the reorder)
- Wording problem I spotted: "be eighteen years of age or older" under "You can apply if you:"
  reads badly

## v5: ask the model for sentence-style eligibility (prompt change)
- Wording started "You can apply if you ..." as I wanted
- But content got worse: 7 of 10 rules complete, 1 partial, 2 missing, 0 flipped (v4 was 9 of 10)
  - dropped "eligible to work in your country"
  - employee rule lost "or an Organization or any of its affiliates"
  - still missing "not an Organization Administrator or Mentor"
- I had not touched the cannot_apply_if prompt, yet its output changed
- Lesson: one prompt edit shifts all the other answers. Re-check every field after any change

## v6: back to the v4 prompt, code does the wording
- Restored the v4 eligibility prompt. Added as_sentence() and as_cannot() in notify.py
  to turn "be eighteen years of age" into "are eighteen years of age" (grammar by plain code)
- Result: 9 of 10 rules, 0 flipped. Identical to v4, because temperature 0 gives repeatable output
- Found while reading the output: one disqualifier line has no "you"
  ("You cannot apply if otherwise prohibited ..."), so the code needs a special case for it
- Notification tap: removed tap-to-open-link, added an "Open official page" button instead,
  so the full message can be read in the ntfy app first
- Phone check: wording reads correctly ("are eighteen years of age or older").
  Tapping the notification opens the ntfy app, and the official-page link is at the end of the message.
  Tapping the message text in the app copies it (ntfy default), so the link is what to tap.

## v7: found a hidden regression, then isolated program-specific rules
- After I edited the shared DATES_PROMPT for Outreachy (year and time rules), GSoC total_dates_found
  dropped from 9 to 0. dates stayed empty, so the output still looked right
- The code-side filter hid the failure: an empty list looked correct by luck.
  Compare-Object against the saved v6 file caught it
- Cause still unknown (year rule, time rule, example, or line-joining)
- Fix: GSoC uses the exact v6 prompt. Outreachy-only rules live in EXTRA_DATE_RULES,
  and line-joining runs only for Outreachy
- Added a plain-code cross-check: count date-looking lines on the page and warn when the model
  returns fewer than 70 percent of them
- Result: GSoC total_dates_found is back to 9, output identical to v6 apart from the snapshot date
- notify.py: the disqualifier header is now "You cannot apply if:" and each line keeps its own
  "you...", because Outreachy rules have other shapes ("your visa must allow...")
- Lesson: a shared prompt is shared risk. Keep program-specific rules separate

## Outreachy: what the pages showed (early Oct 2026)
- Dec 2026 round: initial applications closed Aug 31. Dates still ahead (results Oct 5,
  contribution period Oct 5 to Nov 2, final application Nov 2, interns announced Nov 30)
  are only for people already approved, so they must not become reminders for a new applicant
- Students in India count as northern hemisphere, so they can only apply to the May-Aug round.
  Non-students can apply to either round. My friend does not have to be a student
- The eligibility page says its rules are for the Dec 2026 round and may change
- Page layout differs from GSoC: tab-separated table, year next to each date, wrapped lines
- Left out the Feb 2026 page (last season) and the diversity statistics paragraph
  (could be misread as a list of eligible groups; the page says there is no such list)
- Outreachy bans generative AI in initial application essays, so the tool only relays page text
  and never writes essays

| | v1 | v2 | v3 | v4 | v5 | v6 | v7 |
|---|---|---|---|---|---|---|---|
| dates | 3 wrong, 1 missing, past dates included | correct (empty) | correct (empty) | correct (empty) | correct (empty) | correct (empty) | correct (empty), 9 of 9 found after fix |
| eligibility | 4 of 6 found | all found, 3 junk lines + 1 wrong | all found, 1 flipped | 9 of 10, 0 flipped | 7 of 10 complete, 1 partial, 0 flipped | 9 of 10, 0 flipped | 9 of 10, 0 flipped |
| typical_timing | month labels lost | copied exact 2026 dates | correct (code) | correct (code) | correct (code) | correct (code) | correct (code) |

## Design lessons so far
1. Use the AI only where it adds something (reading messy text). Dates, filtering, month lists, grammar fixes and source links are done by code
2. One focused job per prompt works better than one big prompt
3. Never let the model decide what is "in the future". Code does that
4. Every message shows the source link and the snapshot date so my friend can verify
5. Wrong-but-believable answers are worse than missing ones, so I check every output by hand
6. Test the output on a real phone, not just in the terminal. That is how I found the cut-off messages
7. After any prompt change, re-check every field, not just the one I edited (v5)
8. A shared prompt is shared risk. Keep rules that only one program needs in a separate setting

## Still to do
- Email backup
- Scheduler: 7 days and 1 day before each date, at 5:30 PM IST
- Other programs: Outreachy, LFX, Season of KDE
- Refresh script and "dates changed" alert
- Give it to my friend and write down what they said