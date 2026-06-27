# GMATDebriefs — Dashboard v.13

Self-contained dashboard over r/GMAT **and** GMAT Club debriefs since Jan 2025.
Open `dashboard_v13.html` in a browser; all data is embedded, no server needed.

## What's new in v.13

v.13 rebuilds the tactic classification used by:

- **Which section tactics show up with higher scores?**
- **What each score tier actually did**
- the tactic chips on each post detail page

The old v.12 labels were too loose. For example, `Q: TTP grind` could appear on
posts where the author never actually mentioned TTP. In v.13, `build_tactics.py`
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
| `dashboard_v13.html` | The dashboard. Self-contained data + detail pages. |
| `debriefs.json` | Per-post rows with v.13 `strategy_items`; old labels preserved in `strategy_items_old_v12`. |
| `post_details.json` | Detail-page model: timeline, Q/V/DI write-ups, tactic chips, body. |
| `build_tactics.py` | Reclassifies tactics from author-side text and writes `tactic_audit_v13.json`. |
| `build_detail.py` | Builds `post_details.json` from `debriefs.json` + corpus. |
| `build_v13.py` | Builds `dashboard_v13.html`. |
| `reddit_corpus.json`, `corpus_index.json` | Full post bodies for Reddit + GMAT Club. |

## Rebuild

```bash
python3 build_tactics.py    # corpus -> fresh strategy_items in debriefs.json
python3 build_detail.py     # debriefs.json + corpus -> post_details.json
python3 build_v13.py        # -> dashboard_v13.html
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
