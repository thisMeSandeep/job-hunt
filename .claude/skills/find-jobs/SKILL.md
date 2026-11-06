---
name: find-jobs
description: Run the full job search pipeline. Pulls jobs from the public job boards of companies in companies.json, uses the discovery agent to search the web for other matches, validates and deduplicates jobs/raw.jsonl, scores new jobs with the screener agent, and shows a ranked shortlist with job ids. Use when the user asks to find jobs, search for jobs, refresh jobs, or see new matches.
argument-hint: "[optional focus, e.g. 'remote only', 'AI Engineer roles', or 'companies: Stripe, Notion']"
---

# Find and rank jobs

All job data commands go through `python3 scripts/jobs.py`. Run `python3 scripts/jobs.py -h` for details.

## Steps

1. **Check the profile.** Read `profile.json`. If it does not exist, contains `FILL IN`, or if `target_roles` or `locations` is empty, stop and tell the user to run `/setup-profile` first. Searching with a placeholder profile returns useless results.

2. **Pull from job boards (main source).** If `companies.json` exists and has at least one company whose slug is not `FILL IN`, run:
   ```bash
   python3 scripts/jobs.py fetch
   ```
   - Add `--company <name>` (repeatable) if the user named specific companies that are already in the file.
   - If the user named companies that are not in the file, run `python3 scripts/jobs.py detect "<Company>"` for each one. Check the board name or sample job to confirm it is the right company, add it to `companies.json`, and then fetch.
   - If a company shows "board not found", run `detect` for it and fix its entry.
   - If `companies.json` is missing or still holds only the example, skip this step and suggest adding target companies at the end (the user can run `/setup-profile` to add them).

3. **Search the web for anything else.** Start the `discovery` agent with the Agent tool (`subagent_type: discovery`). Pass along:
   - The focus from `$ARGUMENTS`, if any.
   - The list of companies in `companies.json`, so it skips them (they were already fetched).
   - A reminder that every record needs `company`, `title`, `location`, `url`, `date_found`, and `source`, and that it must not use LinkedIn or Indeed or log in anywhere.

   If the user asked for only their listed companies, skip this step.

4. **Validate and add ids.**
   ```bash
   python3 scripts/jobs.py check --fix
   ```
   This removes duplicates (same id, same URL, or same company and title) and adds an `id` to records that lack one. Fix other missing fields only when the posting has the information. Otherwise tell the user which records are incomplete.

5. **Screen.** If `python3 scripts/jobs.py unscored --count` is above 0, start the `screener` agent (`subagent_type: screener`). It scores the unscored jobs in batches.

6. **Report.** Show the user:
   - How many new jobs came from the boards and from the web, and any companies or sources that failed or blocked access
   - The ranked table from `python3 scripts/jobs.py top --since <today>`. If that is empty, use `python3 scripts/jobs.py top`. Add the main gaps for each job from `jobs/scored.jsonl`.

7. **Stop and let the user choose.** Ask which jobs they want to pursue. Tell them to run `/apply <id>`, for example `/apply 6fe32ae5`. Ids are permanent, so they work in later sessions too. Do not tailor or apply to anything until the user chooses.

## If nothing is found

Say so plainly. Suggest one or two concrete changes:
- Loosen `title_include`, `title_exclude`, or `locations_include` in `companies.json`. The fetch output shows how many jobs each filter removed.
- Add more companies with `python3 scripts/jobs.py detect "<Company>"`.
- Add more role titles or locations to the profile.
