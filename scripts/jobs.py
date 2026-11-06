#!/usr/bin/env python3
"""Job data tool for this repo. Python 3.9+, standard library only.

Commands:
  fetch      Pull jobs from the public job boards listed in companies.json into jobs/raw.jsonl
  detect     Find which job board a company uses:   detect "Acme Corp" [extra-slug ...]
  check      Validate a jobs file. --fix removes duplicates and adds missing ids.
  find       Look up jobs by id, URL, or words in the company and title
  unscored   Print jobs in jobs/raw.jsonl that are not in jobs/scored.jsonl yet
  top        Print the best scored jobs as a table

Run `python3 scripts/jobs.py <command> -h` for options.

Job ids: every job has an 8-character `id`, a hash of its normalized URL. The same
posting always gets the same id, so ids work across raw.jsonl, scored.jsonl,
tracker.csv, and applications/ folder names.
"""
import argparse
import hashlib
import html
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "jobs" / "raw.jsonl"
SCORED = ROOT / "jobs" / "scored.jsonl"
COMPANIES = ROOT / "companies.json"

REQUIRED = ["id", "company", "title", "location", "url", "date_found", "source"]
USER_AGENT = "job-hunt-cli/1.0"
DESC_LIMIT = 3000  # characters of description kept per job
TRACKING_PARAMS = {"ref", "src", "source", "gh_src", "lever-source", "lever-origin", "trk", "refid"}
ATS_LIST = ["greenhouse", "lever", "ashby", "workable"]


# ---------- helpers ----------

def norm(s):
    return " ".join(str(s or "").lower().split())


def norm_url(u):
    """Lowercase host, drop www., trailing slash, fragment, and tracking params.
    Keep meaningful params such as Greenhouse's gh_jid."""
    if not u:
        return ""
    p = urlsplit(str(u).strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    params = sorted(
        (k, v) for k, v in parse_qsl(p.query)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    )
    return host + p.path.rstrip("/") + ("?" + urlencode(params) if params else "")


def job_id(job):
    key = norm_url(job.get("url")) or f"{norm(job.get('company'))}|{norm(job.get('title'))}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


def read_jsonl(path):
    """Return (lineno, line, obj_or_None, error_or_None) for each non-empty line."""
    rows = []
    if not path.exists():
        return rows
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            rows.append((i, line, obj if isinstance(obj, dict) else None,
                         None if isinstance(obj, dict) else "not a JSON object"))
        except json.JSONDecodeError as e:
            rows.append((i, line, None, str(e)))
    return rows


def load_jobs(path):
    return [o for _, _, o, _ in read_jsonl(path) if o is not None]


def append_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = ""
    if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n"):
        prefix = "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(prefix + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))


class Seen:
    """Duplicate detection: same id, same normalized URL, or same company + title."""

    def __init__(self):
        self.ids, self.urls, self.ct = {}, {}, {}

    @staticmethod
    def _ct(job):
        c, t = norm(job.get("company")), norm(job.get("title"))
        return (c, t) if c and t else None

    def match(self, job):
        if job.get("id") and job["id"] in self.ids:
            return self.ids[job["id"]]
        u = norm_url(job.get("url"))
        if u and u in self.urls:
            return self.urls[u]
        ct = self._ct(job)
        if ct and ct in self.ct:
            return self.ct[ct]
        return None

    def add(self, job, marker=True):
        if job.get("id"):
            self.ids.setdefault(job["id"], marker)
        u = norm_url(job.get("url"))
        if u:
            self.urls.setdefault(u, marker)
        ct = self._ct(job)
        if ct:
            self.ct.setdefault(ct, marker)


# ---------- job board fetchers ----------

# Try IPv4 addresses before IPv6. On networks without working IPv6, Python otherwise
# waits a full timeout on each IPv6 address (40s+ per request for Ashby and Workable).
_getaddrinfo = socket.getaddrinfo


def _ipv4_first(*args, **kwargs):
    return sorted(_getaddrinfo(*args, **kwargs), key=lambda r: r[0] != socket.AF_INET)


socket.getaddrinfo = _ipv4_first


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def strip_html(s):
    s = html.unescape(s or "")  # Greenhouse sends entity-escaped HTML
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>|</tr>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "- ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def clip(s):
    s = (s or "").strip()
    return s if len(s) <= DESC_LIMIT else s[:DESC_LIMIT].rsplit(" ", 1)[0] + " ..."


def to_date(v):
    if v in (None, ""):
        return ""
    if isinstance(v, (int, float)):  # Lever: epoch milliseconds
        return datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat()
    return str(v)[:10]


def fetch_greenhouse(slug, cfg):
    d = http_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(slug)}/jobs?content=true")
    out = []
    for j in d.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        out.append({
            "title": j.get("title", ""),
            "location": loc,
            "remote_policy": "remote" if "remote" in loc.lower() else "",
            "url": j.get("absolute_url", ""),
            "date_posted": to_date(j.get("first_published") or j.get("updated_at")),
            "department": ", ".join(x.get("name", "") for x in j.get("departments") or []),
            "description": strip_html(j.get("content")),
        })
    return out


def fetch_lever(slug, cfg):
    host = "api.eu.lever.co" if cfg.get("region") == "eu" else "api.lever.co"
    d = http_json(f"https://{host}/v0/postings/{quote(slug)}?mode=json")
    out = []
    for j in d if isinstance(d, list) else []:
        cats = j.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location")]
        parts = [j.get("descriptionPlain") or ""]
        for lst in j.get("lists") or []:
            parts.append(f"{lst.get('text', '')}\n{strip_html(lst.get('content'))}")
        parts.append(j.get("additionalPlain") or "")
        out.append({
            "title": j.get("text", ""),
            "location": "; ".join(x for x in locs if x),
            "remote_policy": (j.get("workplaceType") or "").replace("unspecified", ""),
            "url": j.get("hostedUrl", ""),
            "date_posted": to_date(j.get("createdAt")),
            "department": cats.get("team") or "",
            "employment_type": cats.get("commitment") or "",
            "description": "\n".join(p.strip() for p in parts if p.strip()),
        })
    return out


def fetch_ashby(slug, cfg):
    d = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(slug)}?includeCompensation=true")
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""]
        for s in j.get("secondaryLocations") or []:
            locs.append(s.get("location", "") if isinstance(s, dict) else str(s))
        remote = j.get("workplaceType") or ("Remote" if j.get("isRemote") else "")
        out.append({
            "title": j.get("title", ""),
            "location": "; ".join(dict.fromkeys(x for x in locs if x)),
            "remote_policy": str(remote).lower(),
            "url": j.get("jobUrl", ""),
            "date_posted": to_date(j.get("publishedAt")),
            "department": j.get("department") or "",
            "employment_type": j.get("employmentType") or "",
            "salary": (j.get("compensation") or {}).get("compensationTierSummary") or "",
            "description": j.get("descriptionPlain") or "",
        })
    return out


def fetch_workable(slug, cfg):
    d = http_json(f"https://apply.workable.com/api/v1/widget/accounts/{quote(slug)}?details=true")
    out = []
    for j in d.get("jobs", []):
        locs = j.get("locations") or [{"city": j.get("city"), "region": j.get("state"), "country": j.get("country")}]
        loc_strs = [
            ", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x)
            for l in locs if not l.get("hidden")
        ]
        out.append({
            "title": j.get("title", ""),
            "location": "; ".join(x for x in loc_strs if x),
            "remote_policy": "remote" if j.get("telecommuting") else "",
            "url": j.get("url") or j.get("shortlink") or "",
            "date_posted": to_date(j.get("published_on") or j.get("created_at")),
            "department": j.get("department") or "",
            "employment_type": j.get("employment_type") or "",
            "experience_level": j.get("experience") or "",
            "description": strip_html(j.get("description")),
        })
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
}


# ---------- filters ----------

def keyword_hit(keywords, text):
    """Whole-word match, so 'intern' does not match 'internal' and 'ai' does not match 'maintain'."""
    return any(re.search(r"\b" + re.escape(k) + r"s?\b", text) for k in keywords)


def filter_reason(job, f, cutoff):
    title = norm(job["title"])
    inc = [norm(k) for k in f.get("title_include", []) if str(k).strip()]
    exc = [norm(k) for k in f.get("title_exclude", []) if str(k).strip()]
    locs = [norm(k) for k in f.get("locations_include", []) if str(k).strip()]
    if inc and not keyword_hit(inc, title):
        return "title"
    if exc and keyword_hit(exc, title):
        return "title"
    if locs:
        where = norm(job.get("location")) + " " + norm(job.get("remote_policy"))
        if job.get("location") and not keyword_hit(locs, where):
            return "location"
    if cutoff and job.get("date_posted") and job["date_posted"] < cutoff:
        return "age"
    return None


# ---------- commands ----------

def load_companies(path):
    if not path.exists():
        sys.exit(f"{path.name} not found. Copy companies.example.json to companies.json, "
                 f"or run /setup-profile.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{path.name} is not valid JSON: {e}")


def cmd_fetch(a):
    cfg = load_companies(Path(a.companies))
    filters = cfg.get("filters", {})
    companies = [c for c in cfg.get("companies", []) if c.get("ats") and c.get("slug")]
    if a.company:
        wanted = {norm(x) for x in a.company}
        companies = [c for c in companies if norm(c.get("name")) in wanted or norm(c["slug"]) in wanted]
    if not companies:
        sys.exit("No companies to fetch. Add entries to companies.json "
                 '(e.g. {"name": "Acme", "ats": "greenhouse", "slug": "acme"}).')

    max_age = a.max_age_days if a.max_age_days is not None else filters.get("max_age_days", 0)
    cutoff = (date.today() - timedelta(days=max_age)).isoformat() if max_age else ""
    today = date.today().isoformat()
    out_path = Path(a.out)

    seen = Seen()
    for j in load_jobs(out_path):
        seen.add(j)

    new, this_run = [], {}
    print(f"{'company':<24} {'board':<11} {'open':>5} {'match':>6} {'new':>5}  note")
    for c in companies:
        ats, slug, name = c["ats"].lower(), c["slug"], c.get("name") or c["slug"]
        note, fetched, matched, added = "", 0, 0, 0
        skipped = {"title": 0, "location": 0, "age": 0}
        if ats not in FETCHERS:
            note = f"unknown board '{ats}' (use one of: {', '.join(ATS_LIST)})"
        else:
            try:
                jobs = FETCHERS[ats](slug, c)
                fetched = len(jobs)
            except urllib.error.HTTPError as e:
                jobs = []
                note = ("board not found, check the slug with: detect" if e.code == 404
                        else f"HTTP {e.code}, skipped")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                jobs = []
                note = f"failed: {e}"
            for j in jobs:
                reason = filter_reason(j, filters, cutoff)
                if reason:
                    skipped[reason] += 1
                    continue
                matched += 1
                rec = {"id": "", "company": name, "title": j["title"].strip(),
                       "location": j.get("location", ""), "url": j["url"],
                       "date_posted": j.get("date_posted", ""), "date_found": today,
                       "source": f"{ats}-api"}
                for k in ("remote_policy", "department", "employment_type", "experience_level",
                          "salary"):
                    if j.get(k):
                        rec[k] = j[k]
                rec["description"] = clip(j.get("description"))
                rec["id"] = job_id(rec)

                # Same company + title found twice in this run: one record, merged locations.
                key = (norm(name), norm(rec["title"]))
                if key in this_run:
                    first = this_run[key]
                    if rec["location"] and rec["location"] not in first["location"]:
                        first["location"] = "; ".join(x for x in [first["location"], rec["location"]] if x)
                    continue
                if seen.match(rec):
                    continue
                seen.add(rec)
                this_run[key] = rec
                new.append(rec)
                added += 1
            if not note and fetched:
                parts = [f"{v} {k}" for k, v in skipped.items() if v]
                note = ("filtered out: " + ", ".join(parts)) if parts else ""
        print(f"{name[:24]:<24} {ats:<11} {fetched:>5} {matched:>6} {added:>5}  {note}")
        time.sleep(0.3)

    if new and not a.dry_run:
        append_jsonl(out_path, new)
    verb = "would add" if a.dry_run else "added"
    print(f"\n{verb} {len(new)} new jobs to {out_path.relative_to(ROOT) if out_path.is_relative_to(ROOT) else out_path}")
    if len(new) > 100:
        print("That is a lot. Consider tightening title_include / title_exclude / locations_include "
              "in companies.json so the screener has less to score.")


def cmd_detect(a):
    base = a.name.strip().lower()
    trimmed = re.sub(r"\b(inc|ltd|llc|corp|corporation|limited|gmbh|technologies|technology|labs|hq)\.?$",
                     "", base).strip(" ,.")
    cands = []
    for s in [base, trimmed]:
        for v in (re.sub(r"[^a-z0-9]", "", s), re.sub(r"[^a-z0-9]+", "-", s).strip("-")):
            if v and v not in cands:
                cands.append(v)
    cands += [s for s in a.slugs if s not in cands]

    targets = [("greenhouse", {}), ("lever", {}), ("lever", {"region": "eu"}), ("ashby", {}),
               ("workable", {})]
    hits = []
    for slug in cands:
        for ats, extra in targets:
            try:
                jobs = FETCHERS[ats](slug, extra)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                continue
            board_name = ""
            try:
                if ats == "greenhouse":
                    board_name = http_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(slug)}").get("name", "")
                elif ats == "workable":
                    board_name = http_json(f"https://apply.workable.com/api/v1/widget/accounts/{quote(slug)}").get("name", "")
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                pass
            entry = {"name": a.name, "ats": ats, "slug": slug, **extra}
            hits.append(entry)
            print(f"found: {ats}{' (eu)' if extra else ''} slug '{slug}': {len(jobs)} open jobs"
                  + (f", board name '{board_name}'" if board_name else ""))
            if jobs:
                print(f"  sample job: {jobs[0]['title']} - {jobs[0]['url']}")
            print("  " + json.dumps(entry))
            time.sleep(0.2)
    if len(hits) > 1 or any(h["ats"] == "workable" for h in hits):
        print("\nSlugs are shared across companies, so a match may be a different company with "
              "the same name. Check the board name or sample job before adding it to companies.json.")
    if not hits:
        print(f"No public board found for '{a.name}' (tried slugs: {', '.join(cands)}).")
        print("Check the company's careers page: links to boards.greenhouse.io/<slug>, "
              "jobs.lever.co/<slug>, jobs.ashbyhq.com/<slug>, or apply.workable.com/<slug> "
              "show the slug. Then run detect again with that slug as an extra argument.")
        sys.exit(1)


def cmd_check(a):
    path = Path(a.file)
    if not path.exists():
        print(f"{path} does not exist yet. Nothing to check.")
        return
    seen, kept, bad, missing, dupes, added_ids = Seen(), [], [], [], [], 0
    for lineno, line, obj, err in read_jsonl(path):
        if err:
            bad.append((lineno, err))
            kept.append(line)  # keep it so the user can fix it by hand
            continue
        if not obj.get("id") and a.fix:
            obj = {"id": job_id(obj), **obj}
            line = json.dumps(obj, ensure_ascii=False)
            added_ids += 1
        gaps = [f for f in REQUIRED if not str(obj.get(f, "")).strip()]
        if gaps:
            missing.append((lineno, obj.get("company", "?"), obj.get("title", "?"), gaps))
        first = seen.match(obj)
        if first:
            dupes.append((lineno, first, obj.get("company"), obj.get("title")))
            continue
        seen.add(obj, lineno)
        kept.append(line)

    total = len(kept) + len(dupes)
    print(f"{path.name}: {total} records, {len(dupes)} duplicates, "
          f"{len(missing)} with missing fields, {len(bad)} invalid lines")
    for ln, err in bad:
        print(f"  line {ln}: invalid JSON ({err})")
    for ln, c, t, gaps in missing:
        print(f"  line {ln}: {c} / {t} is missing {', '.join(gaps)}")
    for ln, first, c, t in dupes:
        print(f"  line {ln}: duplicate of line {first} ({c} / {t})")
    if a.fix and (dupes or added_ids):
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"Fixed: removed {len(dupes)} duplicates, added {added_ids} ids. {len(kept)} records remain.")
    elif not a.fix and any("id" in g for _, _, _, g in missing):
        print("Run with --fix to add missing ids.")
    sys.exit(1 if bad or missing else 0)


def find_jobs(query, jobs):
    q = query.strip()
    if re.fullmatch(r"[0-9a-fA-F]{4,8}", q):
        hits = [j for j in jobs if str(j.get("id", "")).startswith(q.lower())]
        if hits:
            return hits
    if "/" in q:
        u = norm_url(q)
        hits = [j for j in jobs if norm_url(j.get("url")) == u]
        if hits:
            return hits
    words = norm(q).split()
    return [j for j in jobs if words and all(w in norm(f"{j.get('company')} {j.get('title')}") for w in words)]


def print_table(jobs):
    print(f"{'id':<9} {'score':>5}  {'company':<20} {'title':<40} {'location':<24} url")
    for j in jobs:
        score = j.get("score", "")
        print(f"{j.get('id', ''):<9} {str(score):>5}  {str(j.get('company', ''))[:20]:<20} "
              f"{str(j.get('title', ''))[:40]:<40} {str(j.get('location', ''))[:24]:<24} {j.get('url', '')}")


def cmd_find(a):
    path = Path(a.file) if a.file else (SCORED if SCORED.exists() else RAW)
    hits = find_jobs(a.query, load_jobs(path))
    if not hits:
        print(f"No job in {path.name} matches '{a.query}'.")
        sys.exit(1)
    if a.json:
        for j in hits:
            print(json.dumps(j, ensure_ascii=False))
    else:
        print_table(hits)


def cmd_unscored(a):
    scored = load_jobs(SCORED)
    ids = {j.get("id") for j in scored if j.get("id")}
    urls = {norm_url(j.get("url")) for j in scored if j.get("url")}
    todo = [j for j in load_jobs(RAW) if j.get("id") not in ids and norm_url(j.get("url")) not in urls]
    if a.count:
        print(len(todo))
        return
    for j in todo[: a.limit or None]:
        print(json.dumps(j, ensure_ascii=False))


def cmd_top(a):
    jobs = [j for j in load_jobs(SCORED) if not j.get("dealbreaker_hit")]
    if a.since:
        jobs = [j for j in jobs if str(j.get("date_found", "")) >= a.since]
    if a.min_score:
        jobs = [j for j in jobs if (j.get("score") or 0) >= a.min_score]
    jobs.sort(key=lambda j: j.get("score") or 0, reverse=True)
    if not jobs:
        print("No scored jobs match.")
        return
    print_table(jobs[: a.n])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="pull jobs from boards in companies.json")
    s.add_argument("--companies", default=str(COMPANIES))
    s.add_argument("--out", default=str(RAW))
    s.add_argument("--company", action="append", help="only this company (name or slug); repeatable")
    s.add_argument("--max-age-days", type=int, help="override filters.max_age_days (0 = no limit)")
    s.add_argument("--dry-run", action="store_true", help="show what would be added, write nothing")
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("detect", help="find a company's job board and slug")
    s.add_argument("name")
    s.add_argument("slugs", nargs="*", help="extra slugs to try")
    s.set_defaults(func=cmd_detect)

    s = sub.add_parser("check", help="validate a jobs file")
    s.add_argument("file", nargs="?", default=str(RAW))
    s.add_argument("--fix", "--dedupe", action="store_true", help="remove duplicates and add missing ids")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("find", help="look up jobs by id, URL, or words")
    s.add_argument("query")
    s.add_argument("--file", help="default: jobs/scored.jsonl, or jobs/raw.jsonl if not scored yet")
    s.add_argument("--json", action="store_true", help="print full records")
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("unscored", help="jobs in raw.jsonl not yet in scored.jsonl")
    s.add_argument("--limit", type=int, default=0)
    s.add_argument("--count", action="store_true")
    s.set_defaults(func=cmd_unscored)

    s = sub.add_parser("top", help="best scored jobs")
    s.add_argument("-n", type=int, default=15)
    s.add_argument("--since", help="only jobs found on or after this date (YYYY-MM-DD)")
    s.add_argument("--min-score", type=int, default=0)
    s.set_defaults(func=cmd_top)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
