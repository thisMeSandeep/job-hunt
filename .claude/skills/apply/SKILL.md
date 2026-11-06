---
name: apply
description: Prepare application drafts for one job the user has chosen. Writes a tailored resume, a cover letter under 200 words, and notes on gaps, then adds the job to tracker.csv as shortlisted. Never submits anything. Use when the user picks a job to pursue or apply to.
argument-hint: "<job id, job URL, or company and title words>"
---

# Prepare an application

## Steps

1. **Find the job.** Run:
   ```bash
   python3 scripts/jobs.py find "$ARGUMENTS" --json
   ```
   It matches a job id (or the first 4 or more characters of one), a URL, or words in the company and title. It searches `jobs/scored.jsonl`.
   - If there is no argument or no match, show `python3 scripts/jobs.py top` and ask the user to pick an id.
   - If more than one job matches, show them with `python3 scripts/jobs.py find "$ARGUMENTS"` and ask which id.
   - If the job is only in `jobs/raw.jsonl` (`find ... --file jobs/raw.jsonl`), run the `screener` agent first.
   - If the user gives a URL that is in neither file, tell them to add it with `/find-jobs` first.

2. **Check for dealbreakers.** If the record has `dealbreaker_hit: true`, show the reason and ask the user whether to continue anyway.

3. **Tailor.** Start the `tailor` agent with the Agent tool (`subagent_type: tailor`). Pass the full job record, including its `id`. The folder is `applications/<company>-<role>-<id>/`, with company and role in lowercase kebab-case (for example `applications/acme-senior-frontend-engineer-6fe32ae5/`). If the description in the record is short, the tailor may open the job URL to read the full posting. Make a PDF of the resume only if the user asked for one.

4. **Check the drafts yourself before showing them.**
   - Every employer, title, date, number, and skill in `resume.md` and `cover.md` must appear in `profile.json` or `resume_base.md`. Remove anything that does not, and add it to `notes.md` as a gap.
   - `cover.md` is under 200 words (`wc -w`).
   - `resume.md` fits on one page (about 600 words or fewer).

5. **Track.** Start the `tracker` agent (`subagent_type: tracker`) to add or update the row for this job id with status `shortlisted` and next_action "Review drafts and submit".

6. **Hand off.** Give the user:
   - Paths to the three files
   - The gaps from `notes.md`
   - The application URL

   Then tell them to review the drafts, submit the application themselves, and run `/job-status applied <id>` once they have applied.

## Rules

- Never submit an application, fill in an online form, or send an email or message.
- Do not log in to any ATS or job site.
- Use only facts from `profile.json` and `resume_base.md`.
