#!/usr/bin/env python3
"""v.14 — per-post detail extractor.

Reads the enriched rows (debriefs.json) plus the full post bodies in the local
corpus (reddit_corpus.json + corpus_index.json) and produces post_details.json:
one rich object per post that powers the new in-page **post detail** view —

  detail[post_id] = {
    "body":      full first-post text (the author's own words),
    "overview":  a short extractive lead (1-2 paragraphs),
    "sections":  {"Q":[..], "V":[..], "DI":[..], "General":[..]}  extractive
                 sentences routed to the section they discuss — "capture all
                 things", in the author's words, not a lossy paraphrase,
    "tactics":   {"Q":[..], "V":[..], "DI":[..]}  the v14 tactic tags rebuilt
                 from the author's own post/replies by build_tactics.py,
    "timeline":  [ {date, score, q,v,di, label, kind, est} ... ]  — prep-start
                 marker + one point per attempt; real scores, dates parsed when
                 the author states them else back-calculated from post date,
    "attempts_n":     number of score points on the timeline,
    "prep_known":     whether prep length was stated (drives the prep marker),
  }

Everything is extractive / rule-based and labelled when estimated, so the page
never invents a claim the author didn't make.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"

# A GMAT-ish total: Focus 205-805 (multiples of 5/10) or legacy 200-800.
SCORE_RE = re.compile(r"\b([2-8][0-9]0|[2-8][0-9]5)\b")


# ---------------------------------------------------------------- helpers ----
def iso(d: date) -> str:
    return d.isoformat()


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def split_sentences(text: str):
    """Sentence-ish split that keeps short list-bullet lines intact."""
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if len(line) < 90 or line.count(".") <= 1:
            out.append(line)
        else:
            parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"’])", line)
            out.extend(p.strip() for p in parts if p.strip())
    return out


def get_op_replies(post_id, corpus_reddit, corpus_gclub):
    """Return the OP’s own reply texts, merged into one string."""
    parts = []
    for corpus in (corpus_reddit, corpus_gclub):
        entry = corpus.get(post_id)
        if not entry:
            continue
        author = (entry.get("author") or "").strip().lower()
        for rep in entry.get("replies") or []:
            if not isinstance(rep, dict):
                continue
            rep_author = (rep.get("author") or "").strip().lower()
            rep_text = (rep.get("text") or rep.get("body") or "").strip()
            if not rep_text:
                continue
            if author and rep_author and author in rep_author:
                parts.append(rep_text)
    return "\n\n".join(parts)


# ---------------------------------------------------------- section routing --
SECT = {
    "Q": [r"\bquant\b", r"\bquantitative\b", r"\bmath(s|ematic)?\b", r"\bq[\s\-]?8[0-9]\b",
          r"\bproblem solving\b", r"\bps\b", r"\balgebra\b", r"\bgeometry\b",
          r"\barithmetic\b", r"\bnumber (propert|theor)", r"\bword problem",
          r"\bq[\s\-]?score\b", r"\bq[\s:=]\s?8", r"\bon quant\b", r"\bin quant\b"],
    "V": [r"\bverbal\b", r"\bcritical reasoning\b", r"\bcr\b", r"\brc\b",
          r"\breading comp", r"\bsentence correction\b", r"\bsc\b",
          r"\bv[\s\-]?8[0-9]\b", r"\bv[\s:=]\s?8", r"\bnon[\- ]?native\b",
          r"\bgrammar\b", r"\bpassages?\b", r"\barguments?\b"],
    "DI": [r"\bdata insight", r"\bdi\b", r"\bd\.i\.", r"\bmsr\b", r"\bmulti[\- ]?source\b",
           r"\bgraphics? interpret", r"\btable analysis\b", r"\btwo[\- ]?part\b",
           r"\bdata sufficiency\b", r"\bds\b", r"\bdi[\s\-]?8[0-9]\b", r"\bdi[\s:=]\s?8"],
}
SECT_RE = {k: re.compile("|".join(v), re.I) for k, v in SECT.items()}
GEN_RE = re.compile(
    r"\b(prep|study|studied|practice|practi[sc]ing|mock|official guide|\bog\b|error log|"
    r"strateg|routine|schedule|review|timing|pacing|time management|guess|mindset|"
    r"anxiety|exam day|test day|resource|course|tutor|week|month|hour)", re.I)
SKIP_RE = re.compile(
    r"^(edit:|update:|ps:|p\.s\.|attachment|thanks|thank you|tl;?dr|disclaimer|"
    r"feel free|dm me|happy to|good luck|cheers|congrat)", re.I)
SEC_TOKEN_RE = re.compile(r"\b[qvd]i?\s?[-:=]?\s?\d{2}\b", re.I)
DATEDSCORE_RE = re.compile(rf"{MONTH_RE}\s*[‘’]?\s*\d{{0,4}}\s*[:\-–—]\s*\d{{3}}", re.I)

_APO = "['‘’]"
NOISE_RE = re.compile(
    r"(looking for.{0,30}study buddy|ping me|dm me|feel free|happy to help|"
    r"all the best|good luck|any (tips|advice|suggestion)|anyone else|"
    r"has anyone|can someone|should i|is it worth|wondering if|"
    r"let me know|hit me up|appreciate|would love|"
    r"attaching my|attached|here" + _APO + r"?s my|see below|above is|"
    r"i" + _APO + r"?m (now |currently )?(preparing|prepping|planning|aiming|targeting)|"
    r"i (want|need|plan|hope|wish|intend) to|"
    r"exposure to|work(ing|ed)? (at|in|for) |"
    r"my exam (is |was )?(scheduled|at \d)|"
    r"i" + _APO + r"?m (pretty )?(happy|thrilled|excited|relieved|glad)|"
    r"just (got off|took|finished|completed) my|"
    r"pending the official|"
    r"(this|it) was (a bit of )?a (shock|surprise|let ?down|disappointment)|"
    r"any good.{0,20}(course|resource|book)|"
    r"can (you|u|anyone) suggest|"
    r"no tutoring pitch|"
    r"my exam started at|"
    r"what" + _APO + r"?s the best (way|resource|course|book))", re.I)

_F_APO = "['‘’]"
FILLER_RE = re.compile(
    r"^(i come from[^,]*,\s*(so\s*)?|"
    r"(to be (honest|fair|frank),?\s*)|"
    r"(honestly,?\s*)|"
    r"(exactly,?\s*)|"
    r"(yeah,?\s*)|"
    r"(right,?\s*)|"
    r"(true,?\s*)|"
    r"(agree[d]?,?\s*)|"
    r"(hey[, ]+)|"
    r"(i (think|believe|feel|found|noticed|realized|learned|decided|would say)\s*(that\s*)?)|"
    r"(what (i did|worked|helped)\s*(was|is)\s*(that\s*)?)|"
    r"(the (thing|key|trick|main thing) (is|was)\s*(that\s*)?)|"
    r"(for me,?\s*)|"
    r"(in my (experience|case|opinion),?\s*)|"
    r"(i" + _F_APO + r"?d (say|recommend|suggest)\s*(that\s*)?)|"
    r"(i would (say|recommend|suggest)\s*(that\s*)?)|"
    r"(basically,?\s*)|"
    r"(so basically,?\s*)|"
    r"(long story short,?\s*))", re.I)

TRAIL_RE = re.compile(
    r"(,?\s*(to be (honest|fair)|honestly|if that makes sense|"
    r"which (is|was) (great|nice|good|helpful)|lol|haha|tbh)\s*\.?)\s*$", re.I)


def is_scoreline(s):
    return bool(DATEDSCORE_RE.search(s)) or len(SEC_TOKEN_RE.findall(s)) >= 2


_A = "[''']"  # apostrophe class


def _deperson(s: str) -> str:
    """Convert first-person prose to third-person summary tone.

    Only rewrites the *leading* pronoun and a few possessive patterns.
    Mid-sentence "I" is left intact to avoid broken grammar.
    """

    # leading "I'd suggest/recommend" → "Recommends"
    s = re.sub(r"^i" + _A + r"?d (suggest|recommend)\b", r"Recommends", s, count=1, flags=re.I)
    s = re.sub(r"^i would (suggest|recommend)\b", r"Recommends", s, count=1, flags=re.I)

    # leading "I verb" → drop the pronoun, keep the verb
    s = re.sub(
        r"^(?:i" + _A + r"?d |i" + _A + r"?m |i" + _A + r"?ve |"
        r"i would |i have |i had |i was |i got |i did |"
        r"i also |i just |i mainly |i mostly |i actually |i basically |"
        r"i initially |i eventually |i primarily |i then |i still |"
        r"i only |i never |i always |i simply |i really |i personally |"
        r"i specifically |i typically |i often |i generally |i )",
        "", s, count=1, flags=re.I)

    # after stripping "I", clean up leftover leading verbs
    s = re.sub(r"^think\s+", "", s, count=1, flags=re.I)
    s = re.sub(r"^believe\s+", "", s, count=1, flags=re.I)

    # possessives: "my issue" → "main issue"; "my strategy" → "the strategy"
    s = re.sub(r"\bmy (main |biggest |primary )?(issue|problem|challenge|weakness|struggle)\b",
               r"main \2", s, flags=re.I)
    s = re.sub(r"\bmy (strategy|approach|method|process|routine|plan|focus|goal|score|review)\b",
               r"the \1", s, flags=re.I)

    return s


def condense(s: str) -> str:
    """Rewrite a raw sentence into a concise third-person strategy summary."""
    s = s.strip()
    s = FILLER_RE.sub("", s).strip()
    s = TRAIL_RE.sub("", s).strip()
    s = re.sub(r"\s+", " ", s)

    # filler adverbs at start
    s = re.sub(r"^(actually|honestly|personally|really),?\s*", "", s, flags=re.I)

    s = _deperson(s)

    # clean up: double spaces, leading punctuation
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[,;.\s]+", "", s).strip()

    if s and s[0].islower():
        s = s[0].upper() + s[1:]

    if len(s) > 130:
        for sep in (" — ", " – ", " - ", "; ", ", but ", ", and ", ", so ", ", which "):
            idx = s.find(sep, 50)
            if 50 < idx < 125:
                s = s[:idx]
                break
        else:
            cut = s[:130].rsplit(" ", 1)[0]
            if len(cut) >= 50:
                s = cut
        s = re.sub(r"\s+(and|or|the|a|an|in|on|at|to|of|for|with|is|was|but|so|as)\s*$",
                   "", s, flags=re.I)
        if not s.endswith("."):
            s = s.rstrip(",;: ") + "."
    return s


def has_strategy_value(s: str) -> bool:
    """Return True if the sentence contains actionable strategy content."""
    if len(s) < 15:
        return False
    if NOISE_RE.search(s):
        return False
    return bool(re.search(
        r"\b(practice[ds]?|drill|grind|focus|master|review|work on|"
        r"solve[ds]?|attempt|complete[ds]?|finish|"
        r"use[ds]?|switch|tr[iy]|start|stop|avoid|skip|"
        r"improve[ds]?|gain|score[ds]?|boost|raise|"
        r"learn|understand|memorize|familiar|comfort|"
        r"approach|strateg|method|technique|framework|process|"
        r"timing|pacing|speed|pace|time manage|"
        r"weak|strong|struggle|issue|problem|mistake|"
        r"mock|test|exam|section|official|"
        r"error log|flashcard|anki|note|"
        r"course|tutor|video|lesson|chapter|module|"
        r"key|critical|important|help|difference|"
        r"recommend|suggest|tip|advice)\b", s, re.I))


def route_sections(sentences):
    sec = {"Q": [], "V": [], "DI": [], "General": []}
    for raw in sentences:
        if SKIP_RE.search(raw) or len(raw) < 15 or is_scoreline(raw):
            continue
        if not has_strategy_value(raw):
            continue
        s = condense(raw)
        if len(s) < 12:
            continue
        hit = False
        for k in ("Q", "V", "DI"):
            if SECT_RE[k].search(raw):
                sec[k].append(s)
                hit = True
        if not hit and GEN_RE.search(raw) and len(s) > 20:
            sec["General"].append(s)
    for k in sec:
        seen, out = set(), []
        for s in sec[k]:
            key = s.lower()[:60]
            if key not in seen:
                seen.add(key)
                out.append(s)
        sec[k] = out
    # General is only an extractive *fallback* (curated posts use a written
    # "overall" summary instead) — cap it so it reads as a summary, not a dump.
    sec["General"] = sec["General"][:3]
    return sec
    return sec


def _score_phrase(row):
    score = row.get("total_score")
    start = row.get("start_score")
    gain = row.get("point_gain")
    if score and start and gain and gain > 0:
        return f"A climb from {start} to {score}"
    if score:
        return f"A {score} debrief"
    return "A GMAT debrief"


def _duration_phrase(row):
    weeks = row.get("prep_weeks")
    if not weeks:
        return ""
    try:
        weeks = float(weeks)
    except (TypeError, ValueError):
        return ""
    if weeks < 1:
        return "after a short final push"
    if weeks.is_integer():
        weeks = int(weeks)
    return f"after {weeks} weeks of prep"


def _split_phrase(row):
    parts = []
    for label, key in (("Q", "q_score"), ("V", "v_score"), ("DI", "di_score")):
        if row.get(key):
            parts.append(f"{label}{row[key]}")
    return f"with {' / '.join(parts)}" if len(parts) >= 2 else ""


def _attempt_phrase(row):
    attempts = row.get("attempts")
    if not attempts:
        return ""
    try:
        attempts = int(attempts)
    except (TypeError, ValueError):
        return ""
    if attempts == 1:
        return "on a first attempt"
    return f"across {attempts} attempts"


def _focus_phrase(row, sections):
    labels = []
    for item in row.get("strategy_items", []):
        if ":" in item:
            labels.append(item.split(":", 1)[1].strip())
    for k in ("General", "Q", "V", "DI"):
        for s in sections.get(k, []) if sections else []:
            labels.append(s.rstrip("."))
    clean, seen = [], set()
    for label in labels:
        label = re.sub(r"^(the author|test-taker)\s+", "", label, flags=re.I).strip()
        label = re.sub(r"\s+", " ", label)
        key = label.lower()[:48]
        if len(label) >= 8 and key not in seen:
            seen.add(key)
            clean.append(label)
        if len(clean) >= 2:
            break
    if clean:
        return "Emphasizes " + " and ".join(clean) + "."
    resources = row.get("resources", [])[:2]
    if resources:
        return "Uses " + " and ".join(resources) + " as named prep resources."
    return ""


def lead_overview(sentences, row, sections=None):
    """A compact third-person summary for the card/detail lead."""
    bits = [_score_phrase(row)]
    for piece in (_duration_phrase(row), _attempt_phrase(row), _split_phrase(row)):
        if piece:
            bits.append(piece)
    lead = " ".join(bits).strip() + "."
    focus = _focus_phrase(row, sections or {})
    if focus:
        lead += " " + focus

    # If metadata is too thin, fall back to a cleaned extractive sentence, but
    # keep it out of first person so newly imported Reddit rows match the older
    # written-summary voice.
    if len(lead) < 35:
        for s in sentences:
            if SKIP_RE.search(s):
                continue
            if len(s) >= 40 and not SCORE_RE.fullmatch(s.strip()):
                lead = condense(s)
                break
    lead = re.sub(r"\bI\b", "the author", lead)
    lead = re.sub(r"\bmy\b", "the author's", lead, flags=re.I)
    lead = re.sub(r"\bme\b", "the author", lead, flags=re.I)
    return lead[:320]


# ----------------------------------------------------------- score history --
def find_dated_scores(body):
    """Pull (date|None, score) pairs the author explicitly wrote.

    Handles the two common debrief shapes, distinguishing a *day* from a *year*
    by the apostrophe / magnitude (this is the whole ballgame — "March 30 - 645"
    is day 30, "Nov '24: 615" is year 2024):
      "Nov '24: 615"  /  "May 2025 - 645"   (month + year, then the score)
      "March 30 - 645" / "August 9 - 695"   (month + day,  then the score)
      "...675 ... on January 19"            (score then a bare month + day)
    Year-less dates get their year inferred later from the post date.
    """
    found = []  # [year|None, month|None, day|None, score, pos]
    # A) Month [day|year] (sep) score
    for m in re.finditer(
            rf"\b{MONTH_RE}(?:\s+(['’]?)(\d{{1,4}})(?:st|nd|rd|th)?)?\s*[:\-–—]\s*(\d{{3}})",
            body, re.I):
        mon = MONTHS[m.group(1)[:3].lower()]
        apos, num, sc = m.group(2), m.group(3), int(m.group(4))
        yr = dy = None
        if num:
            n = int(num)
            if apos or n >= 1000 or n > 31:   # it's a year
                yr = _yr(num)
            else:                              # it's a day-of-month
                dy = n
        if 200 <= sc <= 805:
            found.append([yr, mon, dy, sc, m.start()])
    # B) score ... (on|in) Month [day]
    for m in re.finditer(
            rf"(\d{{3}})[^\n]{{0,40}}?\b(?:on|in)\s+{MONTH_RE}\s*(\d{{1,2}})?", body, re.I):
        sc = int(m.group(1))
        mon = MONTHS[m.group(2)[:3].lower()]
        day = m.group(3)
        if 200 <= sc <= 805:
            found.append([None, mon, int(day) if day else None, sc, m.start()])
    return found


def _yr(tok):
    if not tok:
        return None
    y = int(tok)
    return 2000 + y if y < 100 else y


def arrow_chain(text):
    """Ordered scores from an arrow/`to`/`then` chain, e.g. 615 -> 645 -> 685."""
    best = []
    for m in re.finditer(
            r"(\d{3})(?:\s*(?:->|→|–>|to|then|,|/|→)\s*(\d{3})){1,5}", text):
        nums = [int(x) for x in re.findall(r"\d{3}", m.group(0))
                if 200 <= int(x) <= 805]
        if len(nums) > len(best):
            best = nums
    return best


def build_timeline(row, body):
    post_d = parse_date(row["date"])
    total = row["total_score"]
    start = row.get("start_score")
    prep_w = row.get("prep_weeks")

    # 1) ordered attempt scores -------------------------------------------------
    dated = find_dated_scores(body)
    scores = []
    if dated:
        seen = set()
        for yr, mon, day, sc, _ in dated:
            if sc not in seen:
                seen.add(sc)
                scores.append({"score": sc, "yr": yr, "mon": mon, "day": day})
    if not scores:
        chain = arrow_chain(row["title"]) or arrow_chain(body)
        scores = [{"score": s} for s in chain]
    if not scores:
        seq = []
        if start and start != total:
            seq.append(start)
        seq.append(total)
        scores = [{"score": s} for s in seq]

    have_scores = {s["score"] for s in scores}
    # the row already knows the starting score — recover an attempt the prose
    # parser missed (e.g. "first attempt … yielded 645" with the score after the
    # date). Prepend it only when it's genuinely the lowest, earliest point.
    if start and start != total and start not in have_scores and \
            start < min(have_scores):
        scores.insert(0, {"score": start})
        have_scores.add(start)
    # ensure the official total is the last point
    if total not in have_scores:
        scores.append({"score": total})
    # collapse accidental consecutive dupes
    cleaned = []
    for s in scores:
        if cleaned and cleaned[-1]["score"] == s["score"]:
            continue
        cleaned.append(s)
    scores = cleaned[:10]   # keep the chart readable

    # 2) assign dates -----------------------------------------------------------
    # resolve year for month-only entries: walk backward from the post date
    have_real = any(s.get("mon") for s in scores)
    if have_real:
        ref_y, ref_m = post_d.year, post_d.month
        for s in reversed(scores):
            if s.get("mon"):
                y = s.get("yr")
                if not y:
                    y = ref_y if s["mon"] <= ref_m else ref_y - 1
                day = s.get("day") or 15
                try:
                    s["date"] = iso(date(y, s["mon"], min(day, 28)))
                except ValueError:
                    s["date"] = None
                if s.get("date"):
                    ref_y, ref_m = y, s["mon"]
    # clamp any parsed date to the post date (an attempt can't post-date the write-up)
    final_d = post_d
    for s in scores:
        if s.get("date") and parse_date(s["date"]) > final_d:
            s["date"] = None
    n = len(scores)
    # the official total is the final sitting => anchor it to the post date (exact)
    scores[-1]["date"] = iso(final_d)
    scores[-1].pop("est", None)
    # estimated dates are interpolated *between the real anchors* so an estimated
    # point always sits in its right slot (mixed real/estimated timelines stay in
    # order). Anchors = points the author actually dated + the official + a
    # virtual prep-window start before the first point.
    if prep_w:
        win = timedelta(weeks=prep_w)
    elif n > 1:
        win = timedelta(weeks=12 * (n - 1))
    else:
        win = timedelta(weeks=8)
    real_dates = [parse_date(s["date"]) for s in scores
                  if s.get("date") and not s.get("est")]
    earliest_real = min(real_dates) if real_dates else final_d
    # the virtual start must precede every real-dated point
    virt0 = min(final_d - win, earliest_real - timedelta(weeks=2))
    anchors = [(-1, virt0)]
    for i, s in enumerate(scores):
        if s.get("date") and not s.get("est"):
            anchors.append((i, parse_date(s["date"])))
    if anchors[-1][0] != n - 1:
        anchors.append((n - 1, final_d))
    for i, s in enumerate(scores):
        if s.get("date") and not s.get("est"):
            continue
        prev = max(a for a in anchors if a[0] < i)
        nxt = min((a for a in anchors if a[0] > i), default=(n - 1, final_d))
        span = nxt[0] - prev[0]
        frac = (i - prev[0]) / span if span else 1
        d = prev[1] + timedelta(days=int((nxt[1] - prev[1]).days * frac))
        s["date"] = iso(min(d, final_d))
        s["est"] = True
    # safety: enforce non-decreasing dates by index
    for i in range(1, n):
        if scores[i]["date"] < scores[i - 1]["date"]:
            scores[i]["date"] = scores[i - 1]["date"]

    # 3) build points: prep-start marker + one per reported score ----------------
    pts = []
    prep_known = bool(prep_w)
    if prep_known:
        ps = post_d - timedelta(weeks=prep_w)
        first_sc_d = parse_date(scores[0]["date"])
        if ps >= first_sc_d:
            ps = first_sc_d - timedelta(weeks=2)
        pts.append({"date": iso(ps), "kind": "prep", "label": "Prep started",
                    "est": True, "weeks": prep_w})
    for i, s in enumerate(scores):
        last = i == len(scores) - 1
        pt = {"date": s["date"], "score": s["score"], "kind": "attempt",
              "final": last, "est": bool(s.get("est"))}
        if last:
            pt["q"], pt["v"], pt["di"] = row.get("q_score"), row.get("v_score"), row.get("di_score")
        pts.append(pt)
    return pts, prep_known, len([p for p in pts if p["kind"] == "attempt"])


# ------------------------------------------------------------------- main ----
def main():
    debriefs = json.loads((BASE / "debriefs.json").read_text())
    reddit = json.loads((BASE / "reddit_corpus.json").read_text())
    gclub = json.loads((BASE / "corpus_index.json").read_text())
    # Curated, hand-written third-person summaries (optional). Posts present here
    # get a genuine written summary; everything else falls back to the extractive
    # routing below until it, too, is summarised.
    sfile = BASE / "summaries.json"
    summaries = json.loads(sfile.read_text()) if sfile.exists() else {}

    details = {}
    miss = 0
    curated_n = 0
    for row in debriefs:
        pid = row["post_id"]
        if pid in reddit:
            body = reddit[pid].get("first_post") or ""
        elif pid in gclub:
            body = gclub[pid].get("first_post") or ""
        else:
            body = ""
            miss += 1
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        op_replies = get_op_replies(pid, reddit, gclub)
        full_text = (body + "\n\n" + op_replies).strip() if op_replies else body

        sents = split_sentences(full_text)
        sections = route_sections(sents)
        overall = ""
        cur = summaries.get(pid)
        if cur:
            curated_n += 1
            # Curated summaries may provide only the written "overall" block.
            # In that case keep the generated section notes instead of blanking
            # Q/V/DI; older fully curated entries can still override sections.
            if any(cur.get(k) for k in ("Q", "V", "DI")):
                sections = {
                    "Q": cur.get("Q", sections.get("Q", [])),
                    "V": cur.get("V", sections.get("V", [])),
                    "DI": cur.get("DI", sections.get("DI", [])),
                    "General": [],
                }
            else:
                sections["General"] = []
            overall = cur.get("overall", "")
        tac = {"Q": [], "V": [], "DI": []}
        for s in row.get("strategy_items", []):
            for k in ("Q", "V", "DI"):
                if s.startswith(k + ":"):
                    tac[k].append(s.split(":", 1)[1].strip())
        timeline, prep_known, n_att = build_timeline(row, full_text)

        display_body = body
        if op_replies:
            display_body += "\n\n— Author's replies —\n\n" + op_replies

        details[pid] = {
            "body": display_body,
            "overview": lead_overview(sents, row, sections),
            "sections": sections,
            "overall": overall,
            "tactics": tac,
            "timeline": timeline,
            "attempts_n": n_att,
            "prep_known": prep_known,
        }

    (BASE / "post_details.json").write_text(
        json.dumps(details, ensure_ascii=False, separators=(",", ":")))
    have_sec = sum(1 for d in details.values()
                   if any(d["sections"][k] for k in ("Q", "V", "DI")))
    multi = sum(1 for d in details.values() if d["attempts_n"] >= 2)
    print(f"post_details.json: {len(details)} posts "
          f"({miss} without a body), {have_sec} with Q/V/DI text, "
          f"{multi} with a multi-attempt timeline, "
          f"{curated_n} with a curated summary.")


if __name__ == "__main__":
    main()
