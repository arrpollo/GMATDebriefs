# GMATDebriefs — Dashboard v.15

Self-contained dashboard over achieved-score GMAT debriefs only.
Open `dashboard_v15.html` in a browser; all data is embedded, no server needed.

## What's new in v.15

- Removes Asking Question and Other posts from the dashboard payload and UX.
- Removes the post-type filter.
- Keeps achieved-score debriefs only: 330 rows from the v.14 source data.
- Adds an "Improve by section" band with Quant, Verbal, and Data Insights cards.
- Each section card opens a deeper insight page with differentiators, tactic
  bundles, bottleneck analysis, prep-time outcomes, section-balance scatter,
  heatmap, and matching-debrief views.
- Keeps the v.14 detail page without the former "In their own words" verbatim
  section.

## Rebuild

From this folder:

```bash
python3 build_v15.py
```

The builder writes:

- `dashboard_v15.html`

## Data Notes

- v.15 intentionally embeds only rows tagged `Debrief` in `debriefs.json`.
- Section insight pages use debriefs that report the relevant final section score
  and contain matching section tactics or generated section notes.
- The current data does not contain reliable before/after Q/V/DI section-score
  pairs, so section insight pages focus on final-section patterns, bottlenecks,
  bundles, and total-gain context where available.
- v.14 remains the archival/pipeline folder. v.15 keeps only the files needed to
  build and serve the product dashboard.

## Files

| File | Role |
|------|------|
| `dashboard_v15.html` | The dashboard. Self-contained data + detail pages. |
| `debriefs.json` | Per-post source rows with v.14 strategy items. |
| `post_details.json` | Detail-page model: timeline, Q/V/DI write-ups, tactic chips. |
| `build_v15.py` | Builds `dashboard_v15.html`. |
| `vercel.json` | Routes `/` to the v.15 dashboard. |
