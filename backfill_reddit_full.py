#!/usr/bin/env python3
"""Full Reddit backfill for v.14.

Discovers r/GMAT submissions from 2024-07-01 through today using a public
Reddit archive, filters for likely author-owned GMAT debriefs with achieved
scores >655, deduplicates against v.14, then renders each surviving Reddit post
in Chrome to capture the first post plus comments.

The script is checkpointed:
  - reddit_backfill_candidates.json records discovery/filter decisions.
  - reddit_backfill_log.json records scrape/import results.
  - imported rows are written immediately through scrape_reddit_one.update_json.

Examples:
  python3 backfill_reddit_full.py --discover-only
  python3 backfill_reddit_full.py --headed --profile ../v11/.chrome-profile
  python3 backfill_reddit_full.py --headed --limit 10 --delay 5
"""
import argparse
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

import scrape_reddit_one as one

BASE = Path(__file__).resolve().parent
DEBRIEFS = BASE / "debriefs.json"
CANDIDATES = BASE / "reddit_backfill_candidates.json"
LOG = BASE / "reddit_backfill_log.json"

ARCHIVE_URL = "https://api.pullpush.io/reddit/search/submission/"
START_DATE = "2024-07-01"
DEFAULT_AFTER = int(dt.datetime.fromisoformat(START_DATE).replace(tzinfo=dt.UTC).timestamp())
USER_AGENT = "Mozilla/5.0 Codex GMAT research"


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


DISCOVERY_TERMS = [
    "debrief", "scored", "journey", "ama", "finally", "experience",
    "715", "725", "735", "745", "755", "765", "775", "785", "795",
    "705", "695", "685", "675", "665",
]


def archive_fetch(after, before, size=100, retry=3, q=None):
    params = {
        "subreddit": "GMAT",
        "after": str(after),
        "before": str(before),
        "size": str(size),
        "sort": "asc",
        "sort_type": "created_utc",
    }
    if q:
        params["q"] = q
    url = ARCHIVE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429:
                time.sleep(45 * (attempt + 1))
            else:
                time.sleep(2 * (attempt + 1))
        except Exception as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Archive fetch failed after {retry} tries: {last_exc}")


def iter_archive(after, before, throttle=1.0, q=None):
    seen = set()
    cursor = after
    while cursor < before:
        data = archive_fetch(cursor, before, q=q)
        batch = data.get("data") or []
        if not batch:
            break
        advanced = cursor
        yielded = 0
        for post in batch:
            pid = post.get("id")
            created = int(float(post.get("created_utc") or 0))
            advanced = max(advanced, created)
            if not pid or pid in seen:
                continue
            seen.add(pid)
            yielded += 1
            yield post
        if yielded == 0 and advanced <= cursor:
            break
        cursor = advanced + 1
        if throttle:
            time.sleep(throttle)


def month_windows(after, before):
    start = dt.datetime.fromtimestamp(after, dt.UTC).date().replace(day=1)
    end = dt.datetime.fromtimestamp(before, dt.UTC).date()
    cur = start
    while cur <= end:
        if cur.month == 12:
            nxt = dt.date(cur.year + 1, 1, 1)
        else:
            nxt = dt.date(cur.year, cur.month + 1, 1)
        lo = max(after, int(dt.datetime(cur.year, cur.month, cur.day, tzinfo=dt.UTC).timestamp()))
        hi = min(before, int(dt.datetime(nxt.year, nxt.month, nxt.day, tzinfo=dt.UTC).timestamp()))
        if lo < hi:
            yield cur.isoformat()[:7], lo, hi
        cur = nxt


def norm_title(title):
    return one.norm_title(title)


def iso_from_utc(ts):
    return dt.datetime.fromtimestamp(float(ts), dt.UTC).date().isoformat()


def post_url(post):
    permalink = post.get("permalink") or ""
    if permalink.startswith("http"):
        return permalink
    if permalink.startswith("/"):
        return "https://www.reddit.com" + permalink
    return post.get("url") or ""


SCORE = re.compile(r"\b([2-8][0-9][05])\b")
SECTION_SCORE = re.compile(r"\b(?:q|v|di|d|quant|verbal|data insights?)\s*[-:/=]?\s*(?:6[0-9]|7[0-9]|8[0-9]|90)\b", re.I)
MOCK_CONTEXT = re.compile(r"\b(mock|practice test|practice exam|diagnostic|target|aim(?:ing)?|goal|want|need|hop(?:e|ing)|can i|could i|should i)\b", re.I)


def score_candidates(text):
    vals = []
    for m in SCORE.finditer(text or ""):
        val = int(m.group(1))
        if not 405 <= val <= 805:
            continue
        before = text[max(0, m.start() - 45):m.start()]
        after = text[m.end():m.end() + 45]
        vals.append((val, before, after))
    return vals


def achieved_total(title, body):
    blob = f"{title}\n{body[:2500]}"
    strong = []
    for val, before, after in score_candidates(blob):
        ctx = f"{before} {after}"
        if val <= 655:
            continue
        if re.search(r"\b(scored?|got|received|ended with|finished with|came back with|official|actual|real exam|test center|attempt)\b", ctx, re.I):
            if not MOCK_CONTEXT.search(ctx) or re.search(r"\b(official|actual|real exam|test center)\b", ctx, re.I):
                strong.append(val)
    if strong:
        return max(strong)

    # Titles like "GMAT 725 Debrief", "715 Finally", "675 in first attempt".
    if is_debriefish(title, body):
        title_vals = [v for v, _, _ in score_candidates(title) if v > 655]
        if title_vals and not re.search(r"\b(target|aim|goal|need|can i|should i|mock)\b", title, re.I):
            return max(title_vals)
    return None


STRONG_DEB = re.compile(
    r"\bdebrief\b|\bAMA\b|\bmy (?:gmat )?(?:journey|debrief|story|experience|prep|result)\b|"
    r"\bthank you (?:everyone|all|guys|you all|so much)\b|"
    r"\bhow i (?:went|scored|got|improved|cracked|reached|prepped|studied|jumped|managed|finally)\b|"
    r"\bfrom \d{3}\b.{0,22}?\bto \d{3}\b|\b\d{3}\s*(?:to|->|→)\s*\d{3}\b|"
    r"\bfinally (?:scored|done|did it|made it)\b|\bscored (?:a )?\d{3}\b|\bgot (?:a )?\d{3}\b|"
    r"\b\d(?:st|nd|rd|th) attempt\b|\battempt \d\b",
    re.I,
)
QUESTION_TITLE = re.compile(
    r"\?|^\s*(?:how(?!\s+i\b)|what|which|should|can|could|would|is|are|do|does|did|why|when|where|"
    r"any(?:one|body)?|need|help)\b|"
    r"\b(?:need|seeking|want|looking for) (?:help|advice|suggestions?|guidance|a plan|recommendation)\b|"
    r"\bshould i\b|\bcan i\b|\bcould i\b|\bis it\b|\bhas anyone\b|"
    r"\bpeople who scored\b|\bfor people who\b|\bto \d{3}\+?\s*scorers?\b",
    re.I,
)
PROMO_TITLE = re.compile(
    r"(master gmat|essential tips|pretty easy|perfect 805|805 scorer|common loopholes|"
    r"perfect scorer|ask me anything .*session|ama session|"
    r"stop obsessing|how the experts do it|repetition, repetition|life hacks|takt time)",
    re.I,
)
ADVICE_TITLE = re.compile(
    r"(\?|advice|suggestions?|help|what (?:to|should|do)|should i|can i|could i|"
    r"retake|options|query|looking for|need guidance|before retake|improve\?|"
    r"how should i improve|do i have|chance|possible)",
    re.I,
)
STRICT_TITLE = re.compile(
    r"\bdebrief\b|\bmy (?:gmat )?(?:journey|story|experience)\b|"
    r"\bgmat (?:test )?experience\b|\bhow i (?:went|scored|got|improved|cracked|reached|prepped|studied|jumped|managed)\b|"
    r"\bfrom \d{3}\b.{0,28}?\bto \d{3}\b|\b\d{3}\s*(?:to|->|→)\s*\d{3}\b|"
    r"\bscored? .{0,30}\bAMA\b|\bGMAT .{0,30}\bAMA\b",
    re.I,
)
PREP_CONTENT = re.compile(
    r"\b(prep|stud(?:y|ied|ying)|resources?|mocks?|official guide|og\b|gmat club|"
    r"ttp|e-?gmat|gmat ninja|quant|verbal|data insights?|di\b|cr\b|rc\b|"
    r"strategy|what helped|mistakes?|error log|practice|timing|section order)\b",
    re.I,
)


def is_debriefish(title, body):
    title = title or ""
    body = body or ""
    if PROMO_TITLE.search(title):
        return False
    if STRONG_DEB.search(title):
        return True
    if QUESTION_TITLE.search(title):
        return False
    first = body[:1200]
    return bool(STRONG_DEB.search(first) and re.search(r"\b(I|my)\b", first, re.I))


def is_strict_rendered_debrief(title, body):
    """Final rendered-page guard for rows that will be tagged Debrief.

    Discovery is intentionally broad. Import is intentionally stricter: achieved
    score + advice request is not enough; the rendered post must present a
    debrief/journey/experience or include meaningful prep content.
    """
    title = title or ""
    body = body or ""
    if PROMO_TITLE.search(title):
        return False
    title_strong = bool(STRICT_TITLE.search(title))
    if ADVICE_TITLE.search(title) and not title_strong:
        return False
    if title_strong and len(body) >= 250:
        return True
    if re.search(r"\b(?:scored|got|received|came back with|finished with)\b.{0,35}\b[2-8][0-9][05]\b", title + "\n" + body[:600], re.I):
        return len(body) >= 900 and bool(PREP_CONTENT.search(body))
    return False


def reject_reason(post, existing_ids, existing_titles):
    pid = post.get("id") or ""
    title = post.get("title") or ""
    body = post.get("selftext") or ""
    if pid in existing_ids:
        return "duplicate-id"
    if norm_title(title) in existing_titles:
        return "duplicate-title"
    if not is_debriefish(title, body):
        return "not-debriefish"
    total = achieved_total(title, body)
    if not total:
        return "no-achieved-score-gt-655"
    return ""


def sorted_items(items):
    return sorted(items, key=lambda x: (x["reject_reason"] != "", x["date"], x["id"] or ""))


def make_report(after, before, terms, counts, items, partial=False, last_completed_month=None):
    window = {
        "after": dt.datetime.fromtimestamp(after, dt.UTC).date().isoformat(),
        "before": dt.datetime.fromtimestamp(before, dt.UTC).date().isoformat(),
    }
    if last_completed_month:
        window["last_completed_month"] = last_completed_month
    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "source": "pullpush.io r/GMAT keyword-scoped submissions",
        "terms": terms,
        "window": window,
        "counts": counts,
        "items": sorted_items(items),
        "partial": partial,
    }


def discover(after, before, throttle=1.0, terms=None):
    rows = load_json(DEBRIEFS, [])
    existing_ids = {r.get("post_id") for r in rows}
    existing_titles = {norm_title(r.get("title")) for r in rows}

    previous = load_json(CANDIDATES, None) if CANDIDATES.exists() and after > DEFAULT_AFTER else None
    items = list(previous.get("items", [])) if previous else []
    counts = dict(previous.get("counts", {})) if previous else {}
    seen = {x.get("id") for x in items if x.get("id") and not str(x.get("id")).startswith("archive-error-")}
    scanned = 0
    terms = terms or DISCOVERY_TERMS
    for label, lo, hi in month_windows(after, before):
        month_count = 0
        month_candidates = 0
        print(f"discover {label}...", flush=True)
        for term in terms:
            try:
                posts = list(iter_archive(lo, hi, throttle=throttle, q=term))
            except Exception as exc:
                counts["archive-error"] = counts.get("archive-error", 0) + 1
                items.append({
                    "id": f"archive-error-{label}-{term}",
                    "date": label,
                    "score": None,
                    "num_comments": None,
                    "title": f"Archive error for {label} / {term}: {exc}",
                    "url": "",
                    "archive_total": None,
                    "reject_reason": "archive-error",
                })
                print(f"  archive error term={term}: {exc}", flush=True)
                continue
            term_new = 0
            term_candidates = 0
            for post in posts:
                pid = post.get("id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                scanned += 1
                month_count += 1
                term_new += 1
                reason = reject_reason(post, existing_ids, existing_titles)
                counts[reason or "candidate"] = counts.get(reason or "candidate", 0) + 1
                if not reason:
                    month_candidates += 1
                    term_candidates += 1
                total = achieved_total(post.get("title") or "", post.get("selftext") or "") if not reason or reason == "duplicate-id" else None
                item = {
                    "id": pid,
                    "date": iso_from_utc(post.get("created_utc") or 0),
                    "score": post.get("score"),
                    "num_comments": post.get("num_comments"),
                    "title": post.get("title") or "",
                    "url": post_url(post),
                    "archive_total": total,
                    "matched_term": term,
                    "reject_reason": reason,
                }
                if not reason:
                    item["selftext_preview"] = (post.get("selftext") or "")[:500]
                items.append(item)
            if term_new:
                print(f"  term={term}: {term_new} new, {term_candidates} candidates", flush=True)
        print(f"  {month_count} unique matched submissions, {month_candidates} candidates; total scanned={scanned}", flush=True)
        save_json(CANDIDATES, make_report(after, before, terms, counts, items, partial=True, last_completed_month=label))

    report = make_report(after, before, terms, counts, items)
    save_json(CANDIDATES, report)
    return report


def backfill(args):
    report = load_json(CANDIDATES, None)
    if not report or args.refresh_candidates:
        report = discover(args.after_ts, args.before_ts, throttle=args.archive_delay, terms=args.terms_list)

    done_log = load_json(LOG, {"results": []})
    already_done = {
        r["id"]
        for r in done_log.get("results", [])
        if r.get("status") in ("added", "updated", "duplicate", "skipped", "removed-nondebrief")
    }
    candidates = [x for x in report["items"] if not x.get("reject_reason")]
    if args.only:
        allow = {x.strip() for x in args.only.split(",") if x.strip()}
        candidates = [x for x in candidates if x["id"] in allow]
    if not args.rescrape_done:
        candidates = [x for x in candidates if x["id"] not in already_done]
    if args.limit:
        candidates = candidates[:args.limit]

    print(f"Scrape queue: {len(candidates)} candidate posts")
    if not candidates:
        return

    profile = Path(args.profile)
    if not profile.is_absolute():
        profile = (BASE / profile).resolve()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel="chrome",
            headless=not args.headed,
            viewport={"width": 1280, "height": 900},
            ignore_default_args=["--enable-automation"],
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        for i, cand in enumerate(candidates, 1):
            pid = cand["id"]
            print(f"[{i}/{len(candidates)}] {pid} {cand['date']} {cand['title'][:80]}")
            result = {"id": pid, "title": cand["title"], "url": cand["url"], "date": cand["date"]}
            try:
                rec = one.scrape_one(page, cand["url"])
                if not rec:
                    result.update(status="failed-scrape")
                    print("   failed scrape")
                else:
                    row = one.build_row(pid, rec)
                    # Final guard: rendered page must still look like an own-result debrief.
                    if not is_strict_rendered_debrief(row["title"], rec.get("first_post") or ""):
                        result.update(status="skipped", reason="rendered-not-debriefish")
                        print("   skipped rendered-not-debriefish")
                    else:
                        one.write_markdown(pid, rec)
                        action, total_rows = one.update_json(pid, rec, row)
                        result.update(
                            status=action,
                            score=row["total_score"],
                            q=row["q_score"],
                            v=row["v_score"],
                            di=row["di_score"],
                            n_replies=row["n_replies"],
                            total_rows=total_rows,
                        )
                        print(f"   {action}: score={row['total_score']} comments={row['n_replies']}")
            except SystemExit as exc:
                result.update(status="skipped", reason=str(exc))
                print(f"   skipped: {exc}")
            except Exception as exc:
                result.update(status="error", reason=repr(exc))
                print(f"   error: {exc!r}")
            done_log.setdefault("results", []).append(result)
            done_log["updated_at"] = dt.datetime.now(dt.UTC).isoformat()
            save_json(LOG, done_log)
            if args.delay and i < len(candidates):
                time.sleep(args.delay)

        ctx.close()


def parse_date_to_ts(s):
    d = dt.date.fromisoformat(s)
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.UTC).timestamp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--refresh-candidates", action="store_true")
    ap.add_argument("--before", default=dt.date.today().isoformat())
    ap.add_argument("--after", default=START_DATE)
    ap.add_argument("--archive-delay", type=float, default=1.0)
    ap.add_argument("--terms", default=",".join(DISCOVERY_TERMS))
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--rescrape-done", action="store_true")
    ap.add_argument("--profile", default=str(one.default_profile()))
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    args.before_ts = parse_date_to_ts(args.before) + 86400
    args.after_ts = parse_date_to_ts(args.after)

    terms = [x.strip() for x in args.terms.split(",") if x.strip()]
    args.terms_list = terms
    report = discover(args.after_ts, args.before_ts, throttle=args.archive_delay, terms=terms) if args.discover_only and (args.refresh_candidates or not CANDIDATES.exists()) else load_json(CANDIDATES, None)
    if args.discover_only:
        counts = report["counts"]
        print(f"Discovery written to {CANDIDATES.name}")
        print(f"Candidates: {counts.get('candidate', 0)}")
        for k in sorted(counts):
            print(f"  {k}: {counts[k]}")
        return
    backfill(args)


if __name__ == "__main__":
    main()
