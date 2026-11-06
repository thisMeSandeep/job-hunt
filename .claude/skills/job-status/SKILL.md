---
name: job-status
description: Update or summarize tracker.csv. Use when the user reports an application event (applied, recruiter reply, interview scheduled, offer, rejection, withdrawal) or asks where things stand, what to follow up on, or what is due.
argument-hint: "[update, e.g. 'applied 6fe32ae5', 'applied Acme', or 'interview Acme on 2026-11-12'] — leave empty for a summary"
---

# Track application status

## If `$ARGUMENTS` describes an update

1. Work out which job it is, the new status, and any date or detail. Allowed statuses: `shortlisted`, `applied`, `recruiter_reply`, `interview`, `offer`, `rejected`, `withdrawn`. Map plain words to these, for example "heard back" becomes `recruiter_reply`.
   Identify the job by its `id` (the 8-character job id). If the user gave a company name or words instead, match them against the `id`, company, and title columns of `tracker.csv`. If the job is not in the tracker, use `python3 scripts/jobs.py find "<words>"`.
2. If more than one row or job matches, show the ids and ask which one.
3. Start the `tracker` agent with the Agent tool (`subagent_type: tracker`) and pass the update. Default next actions:
   - `applied`: follow up 7 days after the application date
   - `recruiter_reply`: reply within 2 days
   - `interview`: prepare on the day before the interview
   - `offer`: decide by the deadline the user gives
   - `rejected`, `withdrawn`: no next action
4. Confirm the change in one line.

## If `$ARGUMENTS` is empty or asks for a summary

1. Start the `tracker` agent and ask for a summary.
2. Show:
   - Counts per status
   - Actions due today or overdue: id, company, title, next_action, next_action_date
   - Applications with no update in 14 days or more
3. Suggest the single most useful next step.

## Rules

Do not contact anyone. When a follow-up is due, you may draft the follow-up email into `applications/<company>-<role>-<id>/followup.md` if the user asks, but never send it.
