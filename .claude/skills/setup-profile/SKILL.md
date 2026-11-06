---
name: setup-profile
description: Set up or update the user's job search profile. Fills profile.json and resume_base.md from the user's existing resume (PDF, DOCX, Markdown, or pasted text) and their answers, and sets up companies.json with the target companies whose job boards to check. Use on first run, when profile.json still contains "FILL IN", or when the user wants to change target roles, locations, skills, dealbreakers, or target companies.
argument-hint: "[path to existing resume]"
---

# Set up the job search profile

`profile.json` and `resume_base.md` are the only sources of facts about the user. Every other step depends on them, so they must be accurate and complete.

## Steps

1. If `profile.json`, `resume_base.md`, or `companies.json` does not exist (fresh clone), copy it from `profile.example.json`, `resume_base.example.md`, or `companies.example.json`. Never edit the `.example` files: they are the shared templates. Then read `profile.json` and `resume_base.md` and list every field that is empty or still says `FILL IN`.

2. Get the user's existing resume.
   - If `$ARGUMENTS` is a file path, read it. For PDF use the Read tool. For DOCX, use `pandoc <file> -t markdown` if pandoc is installed. Otherwise ask the user to paste the text.
   - If no path was given, ask the user for a path or for the pasted text.

3. Pull facts from the resume: name, contact line, employers, titles, dates, achievements, projects, skills, education. Copy numbers and dates exactly. Do not round, estimate, or improve them.

4. Ask the user for whatever the resume cannot tell you. Use AskUserQuestion and send all the questions in one batch:
   - Target roles (2 to 5 titles)
   - Locations and remote preference
   - Target company type (for example: product companies, startups, enterprise)
   - Salary expectation or minimum (optional)
   - Dealbreakers (for example: onsite only, contract roles, specific industries)
   - Preferences (team size, domain, tech stack)
   - Companies they would like to work at (optional, as many as they like). These are checked directly on every search, which is the most reliable source of jobs.
   - Which skills are `strong`, `working`, or `learning`. Suggest a split based on the resume and let the user correct it.

5. Write `profile.json`. Keep the existing schema: name, current_employer, years_experience, target_roles, target_company_type, locations, salary_expectation, skills {strong, working, learning}, experience[], projects[], education[], dealbreakers[], preferences[].

6. Write `resume_base.md` in the same section order as the template: header, Summary, Experience, Projects, Skills, Education. Keep it to one page (about 450 to 600 words).

7. Set up `companies.json`:
   - For each target company, run `python3 scripts/jobs.py detect "<Company>"`. Add each confirmed match to `companies`, and check the board name or sample job so you don't add a different company with the same name. List companies with no public board found. Discovery will search for those on the web instead.
   - Remove the `Example Co` placeholder entry.
   - Set `filters` from the profile. `title_include` gets the core words of the target roles (for example "Senior Frontend Engineer" gives "frontend", "engineer"). Keep it broad, because the screener does the fine matching. `title_exclude` gets levels or functions the user clearly does not want (for example "intern", "manager"). `locations_include` gets the user's cities, their common spellings, their country, and "remote" if they accept remote work.
   - Run `python3 scripts/jobs.py fetch --dry-run` and show how many jobs each company would add. If a filter removes almost everything, loosen it.

8. Show the user a short summary of what you filled in. List anything that is still missing or that you were unsure about, and ask them to confirm.

## Rules

- Never invent skills, employers, dates, numbers, or titles. If something is unclear, ask. If the user does not know, leave the field out instead of guessing.
- Do not log in to LinkedIn or any other account to fetch the profile. If the user wants to use their LinkedIn data, ask them to export it or paste it.
- Before you finish, check that no field still contains `FILL IN`. If one does, tell the user which.
