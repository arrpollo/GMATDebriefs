# GMATDebriefs — Dashboard v.12

Self-contained dashboard over r/GMAT **and** GMAT Club debriefs since Jan 2025.
Open `dashboard_v12.html` in a browser — all data is embedded, no server needed.

## What's new in v.12 — the post detail page

In v11, clicking a post jumped **straight to the forum**. In v.12 it opens an
in-page **post detail page** first (one extra hop), and only from there do you go
to the source. Every one of the 267 posts has one. The page has:

- **Back button** (top-left; Esc and the browser Back button also work) that
  returns you to wherever you came from — the table *or* a chart drill-down.
- **At-a-glance summary** — a one-line factual recap (score, percentile, Q/V/DI,
  gain, prep, attempts) plus the author's own opening line, then 8 stat cards.
- **Score timeline chart** — one point per score the author reported, placed on
  the date it was taken. Several attempts ⇒ several points. A dashed **amber line
  marks the prep start**, dated by counting back from the post date using the
  stated prep length. Dates the author wrote are exact (●); the rest are
  estimated and spread across the prep window (◆).
- **Section scores vs typical** — this taker's Q / V / DI against the median of
  debriefs in the same score band, so strengths/weaknesses pop out.
- **Strategy by section (Q / V / DI)** — the author's *own sentences* about each
  section, routed to where they belong (extractive, not a lossy paraphrase — it
  "captures all things"), plus the tactic chips tagged for that post.
- **Resources used** chips, an **Overall approach & mindset** section, and the
  **full debrief verbatim** in a scrollable box.
- **Clear "open the original" link** — in the sticky header *and* a big button at
  the bottom ("Read & reply on the original (Reddit / GMAT Club) ↗").

Everything on the page is extractive / rule-based and labelled when a date is
estimated, so the page never invents a claim the author didn't make.

## Files

| File | Role |
|------|------|
| `dashboard_v12.html` | **The dashboard.** Self-contained (data + detail pages embedded). |
| `debriefs.json` | The flat per-post rows (carried from v11's enrich.py output). |
| `post_details.json` | **The detail-page model** — timeline, Q/V/DI write-ups, body, per post. |
| `build_detail.py` | **Builds `post_details.json`** from `debriefs.json` + the corpus. |
| `build_v12.py` | **The generator.** `debriefs.json` + `post_details.json` → `dashboard_v12.html`. |
| `reddit_corpus.json`, `corpus_index.json` | The full post bodies (Reddit + GMAT Club) the detail builder mines. |

## Rebuild

```bash
python3 build_detail.py     # debriefs.json + corpus -> post_details.json
python3 build_v12.py        # -> dashboard_v12.html
```

`build_v12.py` is pure presentation; `build_detail.py` is the only new logic.
To re-scrape or re-enrich the underlying rows, use the v11 pipeline
(`scrape_full.py` / `scrape_reddit.py` / `enrich.py`) and copy the refreshed
`debriefs.json` + corpus files here.

## How the timeline & strategy are built (`build_detail.py`)

- **Attempt scores** come from a dated "score history" block
  (`Nov '24: 615`, `March 30 - 645`, `…675 … on January 19`), else an arrow chain
  (`615 → 645 → 685`), else `start_score` + `total_score`. A day is told apart from
  a year by the apostrophe/magnitude (`'24` = year, `30` = day-of-month).
- **Dates** the author stated are used as-is; missing ones are interpolated
  *between the real anchors* so mixed real/estimated timelines stay in order. The
  official total is anchored to the post date; the prep marker is `post − prep_weeks`.
- **Q / V / DI text** is the author's sentences, each routed to every section it
  mentions (Focus mapping: DS/MSR/Graphics/Table → Data Insights). Raw
  score-history lines are dropped from the write-up (they live in the timeline).

## Honest limits (carried from v11)

- Samples are small and matching is keyword-based — **directional, not proof**.
- Some timeline dates are **estimated** (labelled ◆); reported scores can mix
  mocks with official sittings where the author didn't distinguish them.
- ~20 GMAT Club rows still lack a clean prep number or full QVDI split because the
  post never states one numerically.
