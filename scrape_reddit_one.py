#!/usr/bin/env python3
"""Import one rendered Reddit debrief into v.14.

Why this exists:
Reddit's JSON endpoints are still unreliable/blocked for this project. The v11
logs showed that the reliable path is to render the post in Chrome and extract
the DOM. This script keeps that path, but scopes it to one URL so v.14 can prove
the H2 2024 backfill works before a larger crawl.

Example:
  python3 scrape_reddit_one.py --url https://www.reddit.com/r/GMAT/comments/1fdfa08/gmat_fe_debrief_from_675_to_735_in_2_weeks/ --headed --profile ../v11/.chrome-profile
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
CORPUS_DIR = BASE / "corpus"
REDDIT_CORPUS = BASE / "reddit_corpus.json"
DEBRIEFS = BASE / "debriefs.json"

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def norm_date(s):
    s = s or ""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b", s)
    if m:
        mon = m.group(2)[:3].title()
        if mon in MONTHS:
            return f"{int(m.group(3)):04d}-{MONTHS.index(mon)+1:02d}-{int(m.group(1)):02d}"
    return ""


NEW_JS = r"""() => {
    const post = document.querySelector('shreddit-post');
    let title='', author='', date='', selftext='';
    if (post) {
        title = post.getAttribute('post-title') || '';
        author = post.getAttribute('author') || '';
        date = post.getAttribute('created-timestamp') || '';
        const body = document.querySelector('div[id^="t3_"][id$="-post-rtjson-content"]')
                  || document.querySelector('[slot="text-body"]')
                  || document.querySelector('[property="schema:articleBody"]');
        selftext = body ? body.innerText.trim() : '';
    }
    const comments = [...document.querySelectorAll('shreddit-comment')].map(c => {
        const body = c.querySelector('[slot="comment"]');
        return {
            author: (c.getAttribute('author') || '').slice(0,80),
            text: body ? body.innerText.trim() : ''
        };
    }).filter(c => c.text);
    return {title, author, date, selftext, comments};
}"""

OLD_JS = r"""() => {
    const main = document.querySelector('#siteTable .thing.link')
              || document.querySelector('.thing.link');
    let title='', author='', date='', selftext='';
    if (main) {
        const t = main.querySelector('a.title');
        title = t ? t.textContent.trim() : '';
        const body = main.querySelector('.expando .usertext-body .md, .usertext-body .md');
        selftext = body ? body.innerText.trim() : '';
        const tm = main.querySelector('.tagline time');
        if (tm) date = tm.getAttribute('datetime') || tm.getAttribute('title') || tm.textContent || '';
        const au = main.querySelector('.tagline .author');
        if (au) author = au.textContent.trim();
    }
    const comments = [...document.querySelectorAll('.commentarea .comment')].map(c => {
        const entry = c.querySelector(':scope > .entry');
        if (!entry) return {author:'', text:''};
        const body = entry.querySelector('.usertext-body .md');
        const au = entry.querySelector('.tagline .author');
        return {
            author: au ? au.textContent.trim().slice(0,80) : '',
            text: body ? body.innerText.replace(/\u23ce/g,'\n').trim() : ''
        };
    }).filter(c => c.text);
    return {title, author, date, selftext, comments};
}"""


def looks_blocked(html):
    h = html.lower()
    return (
        "blocked by network security" in h
        or "whoa there, pardner" in h
        or "you've been blocked" in h
    )


def scrape_one(page, url, verbose=True):
    www_url = url.replace("old.reddit.com", "www.reddit.com")
    old_url = url.replace("www.reddit.com", "old.reddit.com")
    for layout, target_url, js in (("new", www_url, NEW_JS), ("old", old_url, OLD_JS)):
        nav_ok = False
        for attempt in range(3):
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                nav_ok = True
                break
            except Exception as exc:
                msg = str(exc)
                if layout == "new" and "ERR_HTTP_RESPONSE_CODE_FAILURE" in msg and attempt < 2:
                    wait = 8 * (attempt + 1)
                    if verbose:
                        print(f"   rate-limited ({layout}), backoff {wait}s")
                    time.sleep(wait)
                    continue
                if verbose:
                    print(f"   nav error ({layout}): {msg[:90]}")
                break
        if not nav_ok:
            continue
        page.wait_for_timeout(1800)
        if layout == "new":
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1400)
                page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass
        html = page.content()
        if looks_blocked(html):
            if verbose:
                print(f"   [!] blocked ({layout})")
            continue
        try:
            data = page.evaluate(js)
        except Exception as exc:
            if verbose:
                print(f"   eval error ({layout}): {str(exc)[:90]}")
            continue
        if not (data.get("selftext") or data.get("comments")):
            if not (layout == "new" and data.get("title")):
                if verbose:
                    print(f"   [!] empty ({layout}), title={data.get('title','')[:40]!r}")
                continue
        return {
            "url": target_url,
            "title": data.get("title", ""),
            "author": data.get("author", ""),
            "date": norm_date(data.get("date", "")),
            "first_post": data.get("selftext", ""),
            "replies": [
                {"author": c["author"], "text": c["text"]}
                for c in data.get("comments", [])
            ],
            "n_replies": len(data.get("comments", [])),
            "layout": layout,
        }
    return None


def post_id_from_url(url):
    m = re.search(r"/comments/([a-z0-9]+)/", url, re.I)
    if not m:
        raise SystemExit(f"Could not read Reddit post id from URL: {url}")
    return m.group(1)


def norm_title(title):
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


TOTAL_RE = re.compile(r"\b([2-8][0-9][05])\b")
FROM_TO = re.compile(r"from\s+(?:a\s+)?([2-8][0-9][05])\b.{0,35}?\bto\s+([2-8][0-9][05])\b", re.I)
RANGE = re.compile(r"\b([2-8][0-9][05])\s*(?:to|->|-->|>|-)\s*([2-8][0-9][05])\b")
SEC_RE = {
    "q": re.compile(r"(?:\bQ|\bquant(?:itative)?)\s*[-:/=]?\s*(\d{2})\b", re.I),
    "v": re.compile(r"(?:\bV|\bverbal)\s*[-:/=]?\s*(\d{2})\b", re.I),
    "di": re.compile(r"(?:\bDI|\bdata\s*insights?|\bD\.?I\.?|\bD)\s*[-:/=]?\s*(\d{2})\b", re.I),
}


def _hits(rx, text):
    return [
        (m.start(), m.end(), int(m.group(1)))
        for m in rx.finditer(text or "")
        if 60 <= int(m.group(1)) <= 90
    ]


def extract_qvdi(text, total):
    qs, vs, dis = _hits(SEC_RE["q"], text), _hits(SEC_RE["v"], text), _hits(SEC_RE["di"], text)
    official = []
    standalone = []
    for q0, qe, q in qs:
        for v0, ve, v in vs:
            for d0, de, di in dis:
                lo, hi = min(q0, v0, d0), max(qe, ve, de)
                if hi - lo > 90:
                    continue
                nums = [int(x) for x in TOTAL_RE.findall(text[max(0, lo - 22):lo])]
                nums += [int(x) for x in TOTAL_RE.findall(text[hi:hi + 18])]
                if total and total in nums:
                    official.append((lo, q, v, di))
                elif not nums:
                    standalone.append((lo, q, v, di))
    if official:
        _, q, v, di = sorted(official)[0]
        return q, v, di
    if standalone:
        _, q, v, di = sorted(standalone)[0]
        return q, v, di
    return None, None, None


def extract_total_and_start(title, body):
    blob = f"{title}\n{body[:1200]}"
    start = total = None
    m = FROM_TO.search(blob)
    if m:
        start, total = int(m.group(1)), int(m.group(2))
    if total is None:
        m = RANGE.search(title or "")
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b > a:
                start, total = a, b
    if total is None:
        nums = [int(x) for x in TOTAL_RE.findall(title or "")]
        if nums:
            total = max(nums)
    if total is None:
        m = re.search(r"(?:scored?|score|got|result|total|overall)\D{0,20}([2-8][0-9][05])\b", body or "", re.I)
        if m:
            total = int(m.group(1))
    if start is None and total:
        for m in (FROM_TO.finditer(blob)):
            a, b = int(m.group(1)), int(m.group(2))
            if b == total and a < total:
                start = a
                break
    if start and total and start >= total:
        start = None
    return total, start


ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
ATTEMPT_RE = re.compile(
    r"\b(\d|first|second|third|fourth|fifth|sixth)(?:st|nd|rd|th)?\s+"
    r"(?:gmat\s+|official\s+|fe\s+|focus\s+)?attempt\b",
    re.I,
)


def extract_attempts(text):
    best = 0
    for m in ATTEMPT_RE.finditer(text or ""):
        raw = m.group(1).lower()
        best = max(best, ORD.get(raw) or int(raw))
    return best or None


RES_PATTERNS = {
    "Target Test Prep (TTP)": [r"target test prep", r"\bttp\b"],
    "e-GMAT": [r"\be-?\s?gmat", r"\begmat\b"],
    "GMAT Ninja": [r"gmat\s?ninja"],
    "GMATWhiz": [r"gmat\s?whiz"],
    "Magoosh": [r"magoosh"],
    "Manhattan Prep": [r"manhattan"],
    "Official Guide (OG)": [r"official (?:gmat (?:focus )?)?guide", r"\bog\b(?!\w)", r"\bog ?20\d\d"],
    "Official Mocks (mba.com)": [
        r"official mock",
        r"mba\.com",
        r"gmac mock",
        r"official practice (?:exam|test)",
        r"official prep",
    ],
    "GMAT Club": [r"gmat ?club (?:test|mock|quiz|question|cat)", r"gmatclub\.com", r"club tests"],
    "Experts Global": [r"experts?\s*global"],
}
RES_RE = {name: re.compile("|".join(pats), re.I) for name, pats in RES_PATTERNS.items()}
FREE_RESOURCES = {"GMAT Club", "GMAT Ninja", "Official Guide (OG)", "Official Mocks (mba.com)"}


def op_text(rec):
    author = (rec.get("author") or "").strip().lower()
    replies = []
    for rep in rec.get("replies", []):
        rep_author = (rep.get("author") or "").strip().lower()
        if author and rep_author and author in rep_author:
            replies.append(rep.get("text", ""))
    return (rec.get("first_post") or "") + ("\n\n" + "\n\n".join(replies) if replies else "")


def extract_resources(text):
    return [name for name, rx in RES_RE.items() if rx.search(text or "")]


ACCUSE = re.compile(
    r"(is this an? ad\b|is this sponsored|sponsored\?|"
    r"are you (?:affiliated|paid|sponsored|a rep)|affiliated with (?:ttp|e-?gmat|target)|"
    r"\bshill\b|astroturf|paid to promote|"
    r"this is (?:just )?(?:an )?ad\b|reads like an ad|smells like an ad|sounds like an ad|"
    r"do you work for (?:ttp|e-?gmat|target|them)|are you a (?:ttp|company) rep)",
    re.I,
)


def promo_reason(rec):
    for rep in rec.get("replies", []):
        text = rep.get("text", "")
        m = ACCUSE.search(text)
        if m:
            who = (rep.get("author") or "a commenter").split()[0]
            snip = re.sub(r"\s+", " ", text).strip()
            return f"A commenter ({who}) questions if it is promotional: ...{snip[max(0, m.start() - 20):m.start() + 60].strip()}..."
    return ""


def build_row(pid, rec):
    title = rec["title"]
    body = rec.get("first_post") or ""
    total, start = extract_total_and_start(title, body)
    if not total:
        raise SystemExit(f"No GMAT total score found for {pid}: {title}")
    if total <= 655:
        raise SystemExit(f"Skipping {pid}: total score {total} is not >655.")

    q, v, di = extract_qvdi(f"{title}\n{body}", total)
    resources = extract_resources(f"{title}\n{op_text(rec)}")
    tags = ["Debrief"]
    sreason = promo_reason(rec)
    if sreason:
        tags.append("Maybe Promo")
    if not resources or all(r in FREE_RESOURCES for r in resources):
        tags.append("Self Study")

    point_gain = total - start if start and total and total > start else None
    return {
        "post_id": pid,
        "source": "Reddit",
        "date": rec.get("date") or "",
        "permalink": rec["url"].replace("www.reddit.com", "old.reddit.com"),
        "title": title,
        "total_score": total,
        "q_score": q,
        "v_score": v,
        "di_score": di,
        "prep_weeks": None,
        "attempts": extract_attempts(f"{title}\n{body}"),
        "resources": resources,
        "strategy_items": [],
        "start_score": start,
        "point_gain": point_gain,
        "tags": tags,
        "n_replies": rec.get("n_replies"),
        "sreason": sreason,
        "strategy_items_old_v12": [],
    }


def write_markdown(pid, rec):
    CORPUS_DIR.mkdir(exist_ok=True)
    md = [
        f"# {rec['title']}",
        "",
        f"- post_id: {pid}",
        f"- url: {rec['url']}",
        f"- author: {rec.get('author') or 'unknown'}",
        f"- date: {rec.get('date') or 'unknown'}",
        f"- replies: {rec.get('n_replies', 0)}",
        "",
        "## Original post",
        "",
        rec.get("first_post") or "(no selftext)",
        "",
    ]
    for i, rep in enumerate(rec.get("replies", []), 1):
        md.extend([
            f"## Comment {i} - {rep.get('author') or 'unknown'}",
            "",
            rep.get("text") or "",
            "",
        ])
    (CORPUS_DIR / f"{pid}.md").write_text("\n".join(md))


def update_json(pid, rec, row):
    corpus = json.loads(REDDIT_CORPUS.read_text()) if REDDIT_CORPUS.exists() else {}
    corpus[pid] = rec
    REDDIT_CORPUS.write_text(json.dumps(corpus, ensure_ascii=False, indent=1))

    rows = json.loads(DEBRIEFS.read_text())
    existing_idx = next((i for i, r in enumerate(rows) if r.get("post_id") == pid), None)
    existing_titles = {
        norm_title(r.get("title"))
        for r in rows
        if r.get("post_id") != pid
    }
    if norm_title(row["title"]) in existing_titles:
        raise SystemExit(f"Duplicate title already exists: {row['title']}")

    if existing_idx is None:
        rows.append(row)
        action = "added"
    else:
        prev = rows[existing_idx]
        row["strategy_items"] = prev.get("strategy_items", [])
        row["strategy_items_old_v12"] = prev.get("strategy_items_old_v12", [])
        rows[existing_idx] = row
        action = "updated"
    DEBRIEFS.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    return action, len(rows)


def default_profile():
    old = BASE.parent / "v11" / ".chrome-profile"
    if old.exists():
        return old
    return BASE / ".chrome-profile"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--profile", default=str(default_profile()))
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    pid = post_id_from_url(args.url)
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
        rec = scrape_one(page, args.url)
        ctx.close()

    if not rec:
        raise SystemExit("Failed to scrape post in both Reddit layouts.")

    row = build_row(pid, rec)
    write_markdown(pid, rec)
    action, total_rows = update_json(pid, rec, row)

    print(f"{action} {pid}: {row['title']}")
    print(f"date={row['date']} score={row['total_score']} q={row['q_score']} v={row['v_score']} di={row['di_score']}")
    print(f"comments={row['n_replies']} resources={', '.join(row['resources']) or 'none'} tags={', '.join(row['tags'])}")
    print(f"debrief rows file now has {total_rows} total rows")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
