# Build notes

## v1: one prompt for everything (gemma3:4b)
- Dates: 14/18 correct, 1 half-right, 3 wrong, 1 missing
- Wrong dates were all near the end of the list (final evaluations, extended coding)
- Ignored my "only future dates" rule: 16 of 18 dates were already past
- Eligibility: 4 of 6 points found, missed the embargo rule and the "2+ times before" rule
- "start_here" was just link text from the page, not real advice
- Lesson: don't ask a small model to filter dates or do too many jobs at once

## v2: separate prompts, code-side date filter (gemma3:4b)
- dates: correctly empty (all 2026 dates have passed). Gemma found 9 pre-selection dates, code filtered them out
- eligibility: all 8 real rules found now (embargo and "2 or more times" rules fixed)
  but 3 extra lines came from the timeline page's intro text, and one is WRONG:
  "Applicants must be students" (the rules say "a student OR a beginner")
- prepare: 2 right, 1 wrong stage ("submit final work product" is after selection)
- typical_timing: BAD. Gemma copied the exact 2026 dates (including post-selection ones)
  instead of the month-level pattern, and added "Not specified" lines
- Lesson: I ran the "info" prompt on every page, so marketing text and timeline dates leaked in.
  And asking the model to reformat a list is a job plain code does better

