# Job Hunt with Claude Code

A Claude Code project that finds, screens, and prepares job applications for you. Claude finds jobs, scores them against your profile, and writes a tailored resume and cover letter for each job you choose. You review everything and submit it yourself.

## What it does and does not do

**It does:**
- Pull every open job from the companies you choose, straight from their public job boards (Greenhouse, Lever, Ashby, Workable)
- Search the web for matching jobs at other companies
- Score each job against your skills, experience, location, and dealbreakers
- Write a one-page tailored resume and a cover letter under 200 words for each job you choose
- Keep a tracker of your applications and remind you when to follow up

**It does not:**
- Submit applications, send emails, or message anyone
- Scrape LinkedIn or Indeed
- Log in to any account without asking you first
- Invent skills, employers, dates, or numbers. If a job needs something you don't have, it lists it as a gap.

## Requirements

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
- Python 3.9 or later, with no extra packages. Runs `scripts/jobs.py`, which fetches and manages job data.
- Optional: [pandoc](https://pandoc.org/installing.html), to read a `.docx` resume or export a resume to PDF

## Quick start

```bash
git clone <this-repo-url> job-hunt
cd job-hunt
claude
```

Then, inside Claude Code:

```
/setup-profile ~/Documents/my-resume.pdf
```

Claude reads your resume and asks for whatever it doesn't show: target roles, locations, salary, dealbreakers, and the companies you'd like to work at. It then writes `profile.json`, `resume_base.md`, and `companies.json`. Check them before you continue, because every later step uses them.

Then find jobs:

```
/find-jobs
```

## Commands

| Command | What it does |
|---|---|
| `/setup-profile [resume path]` | Creates or updates your profile from your resume and your answers. Run this first. |
| `/find-jobs [focus]` | Finds new jobs, removes duplicates, scores them, and shows a ranked list. |
| `/apply <job id, URL, or company>` | Writes a tailored resume, a cover letter, and notes for one job, then adds the job to the tracker. |
| `/job-status [update]` | Records an update, such as `applied 6fe32ae5` or `applied Acme`, or shows a summary when you give no argument. |

You can also just ask in plain words, for example "find remote frontend jobs" or "I got an interview with Acme on Friday".

## A typical session

```
/find-jobs remote only
```
Claude shows a ranked table:

```
id        score  company  title                 gaps
6fe32ae5     84  Acme     Senior Frontend Eng   GraphQL
a660b830     77  Beta     Full Stack Engineer   Go, Kubernetes
...
```

Pick a job by its id. Ids are permanent, so they still work in a later session:

```
/apply 6fe32ae5
```

Claude writes three files to `applications/acme-senior-frontend-engineer-6fe32ae5/`:
- `resume.md`: your resume, reordered for this job
- `cover.md`: a short cover letter
- `notes.md`: gaps, claims to double-check, and questions the application form may ask

Review and edit them, submit the application on the company's site, then record it:

```
/job-status applied 6fe32ae5
```

Later, see what is due:

```
/job-status
```

## Where jobs come from

1. **Your target companies (main source).** `companies.json` lists companies and the job board each one uses. `/find-jobs` reads those boards' public job lists directly. This is fast, complete, and gives real posting dates. To add a company:
   ```bash
   python3 scripts/jobs.py detect "Acme"
   ```
   This finds which board the company uses. Copy the line it prints into `companies.json`. Check the board name or sample job it shows, because a different company can have the same name.
2. **Web search.** The discovery agent searches career pages and public job boards for matching jobs at companies that are not in your list.

`companies.json` also has filters, applied before Claude scores anything:

```json
"filters": {
  "title_include": ["frontend", "full stack", "engineer"],
  "title_exclude": ["intern", "manager", "director"],
  "locations_include": ["bangalore", "bengaluru", "india", "remote"],
  "max_age_days": 0
}
```

Keywords match whole words, so `intern` does not match "Internal Tools". Keep the filters broad, because the screener does the fine matching. Each fetch prints how many jobs each filter removed, so you can see when a filter is too strict.

## Job ids

Every job gets a permanent 8-character id made from its URL, for example `6fe32ae5`. The same id appears in `jobs/scored.jsonl`, `tracker.csv`, and the job's `applications/` folder, so `/apply` and `/job-status` work with it in any session.

## How jobs are scored

Each job gets a score from 0 to 100:

| Part | Points |
|---|---|
| Skill match | 50 |
| Seniority and experience | 20 |
| Location and remote fit | 15 |
| Company type and preferences | 15 |

A job that hits one of your dealbreakers scores 0. To change the weights, edit `.claude/agents/screener.md`.

## Files

| Path | What it is | In git? |
|---|---|---|
| `profile.example.json`, `resume_base.example.md`, `companies.example.json` | Blank templates | Yes |
| `profile.json` | Your skills, experience, targets, and dealbreakers. The only source of facts about you. | No |
| `resume_base.md` | Your master resume | No |
| `companies.json` | Companies whose job boards are fetched, and filters | No |
| `jobs/raw.jsonl` | Jobs found, one JSON object per line | No |
| `jobs/scored.jsonl` | Jobs with scores, matched skills, and gaps | No |
| `applications/<company>-<role>-<id>/` | Drafts for one job | No |
| `tracker.csv` | Status of every job you are pursuing | No |
| `CLAUDE.md` | Rules Claude follows in this project | Yes |
| `.claude/agents/` | The four agents: discovery, screener, tailor, tracker | Yes |
| `.claude/skills/` | The slash commands above | Yes |
| `scripts/jobs.py` | Fetches, validates, and looks up jobs | Yes |

Your personal files are in `.gitignore`, so you can pull updates or contribute changes without committing your data.

## Customizing

- **Companies and filters:** edit `companies.json`.
- **Web search:** edit `.claude/agents/discovery.md`.
- **Scoring:** edit `.claude/agents/screener.md`.
- **Resume and cover letter style:** edit `.claude/agents/tailor.md` and the Style section of `CLAUDE.md`.
- **Tracker columns and follow-up timing:** edit `.claude/agents/tracker.md` and `.claude/skills/job-status/SKILL.md`.

## Troubleshooting

- **"Run /setup-profile first":** `profile.json` is missing or still has `FILL IN` fields. Run `/setup-profile` or fill in the fields by hand.
- **Few or no jobs found:** loosen the filters in `companies.json`, add companies with `python3 scripts/jobs.py detect "<Company>"`, or add role titles or locations to your profile.
- **"board not found" for a company:** the slug is wrong or the company moved to another board. Run `detect` again, or open the company's careers page and copy the slug from the board's link.
- **A source blocked access:** Claude reports it and moves on. It does not try to get around the block.
- **Slash commands don't appear:** restart Claude Code from the project folder.
- **Work with job data by hand:**
  ```bash
  python3 scripts/jobs.py fetch --dry-run     # preview what would be added
  python3 scripts/jobs.py check --fix         # remove duplicates, add ids
  python3 scripts/jobs.py find "acme"         # look up a job by id, URL, or words
  python3 scripts/jobs.py top -n 20           # best scored jobs
  ```
