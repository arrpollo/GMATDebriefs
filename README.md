# GMATDebriefs — Dashboard v.14

Self-contained dashboard over r/GMAT **and** GMAT Club debriefs, now with the
first successful H2 2024 Reddit backfill case.
Open `dashboard_v14.html` in a browser; all data is embedded, no server needed.

## What's new in v.14

v.14 keeps the v.13 dashboard/classifier/detail pipeline and adds one
non-duplicate r/GMAT debrief from H2 2024 as a proof that the older Reddit gap
can be filled:

- `1fdfa08` — "GMAT FE Debrief: From 675 to 735 in 2 weeks."
- Posted on 2024-09-10 in r/GMAT.
- Scraped from the rendered Reddit page: full first post plus 25 comments.
- Saved in `reddit_corpus.json` and readable form at `corpus/1fdfa08.md`.

The efficient full-run path is:

1. Discover H2 2024 candidates through a public Reddit archive query, because
   direct Reddit `.json` search still returns HTTP 403.
2. Do **not** assume the existing 2025+ Reddit scrape is complete. Re-scan from
   2025 through today as well, then let deduplication prevent repeats.
3. Deduplicate by Reddit post id and normalized title against `debriefs.json`.
4. Render each surviving Reddit URL in Chrome and save full body + comments.
5. Append rows to `debriefs.json`, then run the same v.13 tactic and detail
   builders so classification and summaries stay consistent.

The existing v.13 classifier still powers:

- **Which section tactics show up with higher scores?**
- **What each score tier actually did**
- the tactic chips on each post detail page

The old v.12 labels were too loose. For example, `Q: TTP grind` could appear on
posts where the author never actually mentioned TTP. In v.14, `build_tactics.py`
re-reads each author's post and own replies, ignores other commenters, and writes
fresh `strategy_items` into `debriefs.json`.

Vendor labels are still allowed, but they now require direct author evidence:
TTP, e-GMAT, GMAT Ninja, GMAT Club, Official Guide, and official mocks only get
tagged when the author explicitly says they used them in a prep/action context.
Non-vendor tactics are clearer behavioral groups such as Quant pacing, CR
frameworks, DI timing, error-log review, section-order testing, and test-day
mindset.

## Files

| File | Role |
|------|------|
| `dashboard_v14.html` | The dashboard. Self-contained data + detail pages. |
| `debriefs.json` | Per-post rows with v.14 `strategy_items`; old labels preserved in `strategy_items_old_v12`. |
| `post_details.json` | Detail-page model: timeline, Q/V/DI write-ups, tactic chips, body. |
| `backfill_reddit_full.py` | Discovers and imports Reddit backfill candidates in checkpointed batches. |
| `scrape_reddit_one.py` | Imports one rendered Reddit post + comments into the v.14 corpus and row file. |
| `build_tactics.py` | Reclassifies tactics from author-side text and writes `tactic_audit_v14.json`. |
| `build_detail.py` | Builds `post_details.json` from `debriefs.json` + corpus. |
| `build_v14.py` | Builds `dashboard_v14.html`. |
| `reddit_corpus.json`, `corpus_index.json` | Full post bodies for Reddit + GMAT Club. |
| `corpus/` | Readable Markdown transcripts for newly imported Reddit posts. |

## Rebuild

```bash
python3 backfill_reddit_full.py --discover-only --refresh-candidates --before 2026-06-28 --archive-delay 0.6
python3 backfill_reddit_full.py --headed --profile ../v11/.chrome-profile --delay 4
python3 build_tactics.py    # corpus -> fresh strategy_items in debriefs.json
python3 build_detail.py     # debriefs.json + corpus -> post_details.json
python3 build_v14.py        # -> dashboard_v14.html
```

If the archive rate-limits during discovery, resume from the next unfinished month
with fewer terms and append to the existing checkpoint, for example:

```bash
python3 backfill_reddit_full.py --discover-only --refresh-candidates --after 2025-07-01 --before 2026-06-28 --terms debrief,scored,journey,ama,finally,experience --archive-delay 0.8
```

## Tactic Model

- Labels are rule-based and source-grounded, so they are directional rather than
  causal proof.
- Vendor labels require an author-side mention and an action/prep context.
- Section tactics are grouped under `Q:`, `V:`, or `DI:`. Cross-section habits
  such as mocks, error logs, section order, coaching, and mindset use `General:`.
- Chart labels appear only when at least four debriefs in the active filter use
  the tactic.

## Honest Limits

- Samples are small; use the charts to find patterns and posts to read, not to
  prove that one tactic causes a score.
- Some timeline dates are estimated (labelled ◆); reported scores can mix mocks
  with official sittings where the author did not distinguish them.
- Some GMAT Club rows still lack a clean prep number or full Q/V/DI split because
  the post never states one numerically.
