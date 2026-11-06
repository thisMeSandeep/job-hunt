# Job hunt project

This project helps me find, screen, and apply to jobs. I make the final decision on every application.

## Files
- `profile.json`: my skills, experience, target roles, and dealbreakers. This is the only source of facts about me.
- `resume_base.md`: my master resume.
- `companies.json`: companies whose public job boards are fetched directly, plus title and location filters.
- `profile.example.json`, `resume_base.example.md`, `companies.example.json`: blank templates shared in the repo. `/setup-profile` copies them to create the real files. Never put personal details in the templates.
- `profile.json`, `resume_base.md`, `companies.json`, `jobs/`, `applications/`, and `tracker.csv` are gitignored because they hold personal data.
- `jobs/raw.jsonl`: jobs found by `scripts/jobs.py fetch` and the discovery agent. One JSON object per line.
- `jobs/scored.jsonl`: jobs scored by the screener agent.
- `applications/<company>-<role>-<id>/`: tailored resume and cover letter for one job.
- `tracker.csv`: status of every job I am pursuing.
- `scripts/jobs.py`: fetches, validates, deduplicates, and looks up jobs. Use it instead of reading the large `.jsonl` files whole. Run `python3 scripts/jobs.py -h` for its commands.

## Rules
1. Use only facts from `profile.json` and `resume_base.md`. Never invent skills, employers, dates, numbers, or titles.
2. If a job asks for something not in my profile, list it as a gap. Do not claim it.
3. Never submit an application, send an email, or send a message. Prepare drafts and stop. I will review and send them.
4. Do not scrape LinkedIn or Indeed. Use company career pages, public ATS pages and APIs (Greenhouse, Lever, Ashby, Workable), RSS feeds, and job alert emails.
5. Do not log in to any account without asking me first.
6. Remove duplicate jobs. A job is a duplicate if the id matches, the company and title match, or the URL matches. `python3 scripts/jobs.py check --fix` does this.
7. Every job record must include: id, company, title, location, url, date_found, and source.
8. Every job has a permanent 8-character `id`, a hash of its URL, made by `scripts/jobs.py`. Use it to refer to a job in `jobs/scored.jsonl`, `tracker.csv`, and `applications/` folder names. Never change a job's id.

## Workflow
1. `scripts/jobs.py fetch`: pull jobs from the boards in `companies.json` into `jobs/raw.jsonl`.
2. discovery agent: search the web for other jobs and append them to `jobs/raw.jsonl`.
3. `scripts/jobs.py check --fix`: remove duplicates and add ids.
4. screener agent: score each new job and write `jobs/scored.jsonl`.
5. I choose which jobs to pursue.
6. tailor agent: write a resume and cover letter into the job's folder.
7. tracker agent: update `tracker.csv`.

## Style
Write in plain, direct language. Keep resumes to one page. Keep cover letters under 200 words.
