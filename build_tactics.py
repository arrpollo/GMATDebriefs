#!/usr/bin/env python3
"""v.13 tactic reclassifier.

Rebuilds ``strategy_items`` from the post text itself instead of trusting the
older v11 labels.  The important guardrail: vendor tactics are only assigned
when the author's own post/replies mention the vendor in a prep/action context.
Other commenters are ignored so a reply cannot make a post look like a TTP,
e-GMAT, or GMAT Ninja story.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent


def load_json(name):
    return json.loads((BASE / name).read_text())


def op_replies(entry):
    author = (entry.get("author") or "").strip().lower()
    out = []
    for rep in entry.get("replies") or []:
        if not isinstance(rep, dict):
            continue
        rep_author = (rep.get("author") or "").strip().lower()
        rep_text = (rep.get("text") or rep.get("body") or "").strip()
        if author and rep_author and author in rep_author and rep_text:
            out.append(rep_text)
    return "\n\n".join(out)


def author_text(pid, reddit, gclub):
    for corpus in (reddit, gclub):
        entry = corpus.get(pid)
        if entry:
            first = entry.get("first_post") or ""
            replies = op_replies(entry)
            return (first + ("\n\n" + replies if replies else "")).strip()
    return ""


def sentences(text):
    bits = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])", line)
        bits.extend(p.strip() for p in parts if p.strip())
    return bits


def has(pattern, text):
    return bool(re.search(pattern, text, re.I))


NEG_VENDOR = re.compile(
    r"\b(didn'?t|did not|never|no longer|stopped|avoid(?:ed)?|without|not)\b.{0,45}"
    r"\b(ttp|target test prep|egmat|e-gmat|gmat ninja|gmat club|official guide|og)\b",
    re.I,
)

ACTION = re.compile(
    r"\b(use[ds]?|using|follow(?:ed)?|finish(?:ed)?|complete(?:d)?|subscribe(?:d)?|"
    r"course|program|module|chapter|lesson|video|tutor|tutoring|class|test(?:s)?|"
    r"quiz(?:zes)?|question(?:s)?|practice|drill(?:ed|ing)?|review(?:ed)?|"
    r"prep|study|studied|learn(?:ed|ing)?|rebuild|foundation|help(?:ed|ful)?)\b",
    re.I,
)


def clean_vendor_sentences(sents, vendor_pat):
    out = []
    for s in sents:
        if not has(vendor_pat, s):
            continue
        if NEG_VENDOR.search(s):
            continue
        if ACTION.search(s) or has(r"\b(quant|verbal|di|data insights?|cr|rc|ds)\b", s):
            out.append(s)
    return out


def add(out, label):
    if label not in out:
        out.append(label)


def classify(row, text):
    """Return fresh strategy labels for one post."""
    sents = sentences(text)
    sent_low = [s.lower() for s in sents]
    low = text.lower()
    labels = []

    def any_sent(*patterns):
        return any(all(has(p, s) for p in patterns) for s in sent_low)

    ttp_s = clean_vendor_sentences(sents, r"\b(ttp|target\s+test\s+prep|targettestprep)\b")
    egmat_s = clean_vendor_sentences(sents, r"\be[\s-]?gmat\b")
    ninja_s = clean_vendor_sentences(sents, r"\bgmat\s+ninja\b")
    club_s = clean_vendor_sentences(sents, r"\bgmat\s*club\b")
    og_s = clean_vendor_sentences(sents, r"\b(official guide|og(?:\s|$|[.,;:)])|official verbal|official quant|official di)\b")
    mock_s = clean_vendor_sentences(
        sents, r"\b(official mocks?|official practice (?:test|exam)s?|mba\.com|mock exams?|mock tests?|practice exams?)\b"
    )

    # Vendor/resource tactics. Keep them tied to a section when the resource is
    # commonly or explicitly used for that section; otherwise use General.
    if ttp_s:
        q_context = any(has(r"\b(quant|math|q[ -]?\d{2}|algebra|arithmetic|number propert|geometry)\b", s)
                        for s in ttp_s)
        add(labels, "Q: TTP Quant course" if q_context or len(ttp_s) else "General: TTP course")
    if egmat_s:
        if any(has(r"\b(verbal|cr|critical reasoning|rc|reading comprehension)\b", s) for s in egmat_s):
            add(labels, "V: e-GMAT Verbal course")
        if any(has(r"\b(di|data insights?|data sufficiency|ds|msr|multi[- ]source)\b", s) for s in egmat_s):
            add(labels, "DI: e-GMAT DI practice")
        if not any(x.startswith(("V: e-GMAT", "DI: e-GMAT")) for x in labels):
            add(labels, "General: e-GMAT course")
    if ninja_s:
        if any(has(r"\b(verbal|cr|critical reasoning|rc|reading comprehension)\b", s) for s in ninja_s) or ninja_s:
            add(labels, "V: GMAT Ninja Verbal")
    if club_s:
        if any(has(r"\b(quant|math|q[ -]?\d{2}|question bank|forum quiz|sectional|test)\b", s) for s in club_s):
            add(labels, "Q: GMAT Club Quant sets")
        if any(has(r"\b(di|data insights?|data sufficiency|ds|msr|table|graphics?|sectional)\b", s) for s in club_s):
            add(labels, "DI: GMAT Club DI sets")
        if not any(x.startswith(("Q: GMAT Club", "DI: GMAT Club")) for x in labels):
            add(labels, "General: GMAT Club practice")
    if og_s:
        if any(has(r"\b(quant|math|q[ -]?\d{2})\b", s) for s in og_s):
            add(labels, "Q: Official Guide practice")
        if any(has(r"\b(verbal|cr|critical reasoning|rc|reading comprehension)\b", s) for s in og_s):
            add(labels, "V: Official verbal practice")
        if any(has(r"\b(di|data insights?|data sufficiency|ds|msr|table|graphics?)\b", s) for s in og_s):
            add(labels, "DI: Official DI practice")
        if not any(x.startswith(("Q: Official", "V: Official", "DI: Official")) for x in labels):
            add(labels, "General: Official Guide practice")
    if mock_s:
        add(labels, "General: official mocks & review")

    # Behavior tactics. These fire from the author's text, not from resource tags.
    if has(r"\b(error log|mistake log|wrong answer|incorrect|review(?:ed|ing)? (?:mistakes|errors)|analy[sz]e[ds]? (?:mistakes|errors|mock)|why .* wrong)\b", low):
        add(labels, "General: error log & mistake review")
    if has(r"\b(section order|order of sections|quant[, ]+verbal[, ]+di|verbal[, ]+quant|qvd|vqd|experiment(?:ed)? with .*order|strongest section first|weakest section first)\b", low):
        add(labels, "General: section-order testing")
    if has(r"\b(sleep|warm[- ]?up|anxiety|mindset|calm|panic|confidence|reset|burn(?:ed)? out|stamina|nerves?|jittery)\b", low) or \
            any_sent(r"\b(break|breaks)\b", r"\b(section|exam|test|day|between)\b"):
        add(labels, "General: test-day routine & mindset")
    if has(r"\b(tutor|tutoring|coach|coaching|private class|one[- ]on[- ]one)\b", low):
        add(labels, "General: tutor or coaching")

    q_pat = r"\b(quant|math|q[ -]?\d{2}|algebra|arithmetic|number propert|geometry|word problem)\b"
    v_pat = r"\b(verbal|critical reasoning|cr\b|reading comprehension|rc\b|passage|argument)\b"
    di_pat = r"\b(di|data insights?|data sufficiency|ds\b|multi[- ]source|msr|table analysis|graphics? interpretation|two[- ]part)\b"

    if has(q_pat, low):
        if any_sent(q_pat, r"\b(foundation|fundamental|basic|concept|rebuild|from scratch|weak topic|topic[- ]wise|formula|flashcard|notes?)\b"):
            add(labels, "Q: Quant fundamentals rebuild")
        if any_sent(q_pat, r"\b(timed? sets?|pacing|time management|finish(?:ed)?|move on|skip|guess|educated guess|not get stuck|under two minutes|2 minutes)\b"):
            add(labels, "Q: Quant pacing & move-ons")
        if any_sent(q_pat, r"\b(drill(?:ed|ing)?|practice(?:d)?|questions?|sectional(?:s)?|question bank|hard questions?)\b"):
            add(labels, "Q: Quant targeted drilling")

    if has(v_pat, low):
        if any_sent(v_pat, r"\b(cr|critical reasoning|argument|assumption|weaken|strengthen|prethink|pre-thinking|negation|framework|structure(?:d)? thought)\b"):
            add(labels, "V: CR argument framework")
        if any_sent(v_pat, r"\b(rc|reading comprehension|passage|active read|skim|main idea|tone|inference|read(?:ing)? habit)\b"):
            add(labels, "V: RC active reading")
        if any_sent(v_pat, r"\b(timed? sets?|pacing|time management|finish(?:ed)?|last question|ran out of time|move on|skip|guess)\b"):
            add(labels, "V: Verbal pacing")
        if any_sent(v_pat, r"\b(questions?|official|practice|sentence correction|grammar|drill(?:ed|ing)?)\b"):
            add(labels, "V: Verbal targeted practice")

    if has(di_pat, low):
        if has(r"\b(data sufficiency|ds\b)\b", low):
            add(labels, "DI: Data Sufficiency drilling")
        if has(r"\b(msr|multi[- ]source|table analysis|graphics? interpretation|two[- ]part|charts?|graphs?)\b", low):
            add(labels, "DI: MSR/table/graphics drill")
        if any_sent(di_pat, r"\b(timed? sets?|pacing|time management|finish(?:ed)?|move on|skip|guess|not get stuck|triage|time[- ]consuming)\b"):
            add(labels, "DI: DI timing & triage")
        if any_sent(di_pat, r"\b(questions?|practice|sectional(?:s)?|sub[- ]sectional|drill(?:ed|ing)?)\b"):
            add(labels, "DI: DI targeted practice")
        if has(r"\b(di .*draws? on .*quant.*verbal|master .*quant.*verbal.*di|quant and verbal .*di|q\+v)\b", low):
            add(labels, "DI: build Q+V first")

    return labels


def main():
    rows = load_json("debriefs.json")
    reddit = load_json("reddit_corpus.json")
    gclub = load_json("corpus_index.json")

    old_ttp = new_ttp = 0
    for row in rows:
        old_ttp += "Q: TTP grind" in row.get("strategy_items", [])
        text = author_text(row["post_id"], reddit, gclub)
        labels = classify(row, text)
        new_ttp += "Q: TTP Quant course" in labels
        row["strategy_items_old_v12"] = row.get("strategy_items", [])
        row["strategy_items"] = labels

    (BASE / "debriefs.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))

    counts = Counter(t for r in rows if "Debrief" in r.get("tags", []) for t in r.get("strategy_items", []))
    report = {
        "posts": len(rows),
        "debriefs": sum("Debrief" in r.get("tags", []) for r in rows),
        "old_ttp_grind_count": old_ttp,
        "new_ttp_quant_course_count": new_ttp,
        "tactic_counts_debriefs": dict(counts.most_common()),
    }
    (BASE / "tactic_audit_v13.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Updated strategy_items for {len(rows)} posts.")
    print(f"TTP: old Q: TTP grind={old_ttp}, new Q: TTP Quant course={new_ttp}")
    print("Top debrief tactics:")
    for k, v in counts.most_common(20):
        print(f"{v:3d}  {k}")


if __name__ == "__main__":
    main()
