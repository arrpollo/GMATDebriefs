#!/usr/bin/env python3
"""v.12 — GMATDebriefs.

Presentation only. Reads debriefs.json (enriched by enrich.py) + post_details.json
(per-post detail model built by build_detail.py) and writes a self-contained
dashboard_v12.html.

What changed vs v11 (the v.12 brief): clicking a post no longer jumps straight to
the forum. It opens an in-page **post detail** page first, with a Back button, an
at-a-glance summary, a **score timeline** (one point per reported score + the
back-calculated prep-start), an extractive **Q / V / DI strategy** write-up in the
author's own words, the full debrief text, and a clear **"open the original"** link.
Run build_detail.py before this script.

--- carried over from v11 (vs v10) ---
  1. Vocabulary: "Success Story" -> "Debrief" everywhere (the community's word).
  2. Filter: the meaningless "All" post-type option is gone; you always view one of
     Debrief / Asking Question / Other (defaults to Debrief).
  3. Brand: a real header — GMATDebriefs logo + a top nav with a GMAT tab (the active
     test) and an About tab. The TESTS array makes adding GRE/etc. a one-line change.
  4. Drill-down: clicking a chart no longer spawns a new tab. It opens an in-page
     overlay with a Back button (Esc also closes); only the real forum permalinks
     open externally.
  5. Filters: a single sticky toolbar that follows you down the page, reordered
     (type -> score -> date -> source/resource/attempts/promo), applied live (no
     Apply button), with a proper dual-handle score slider that snaps to real GMAT
     Focus scores (every stop ends in 5).
  6. Charts: shared palette, click-to-drill-down, cleaner axes/tooltips (score
     distribution, weak section by tier, realistic-jump gains, resources, prep-vs-gain
     scatter, Reddit-only tactics heatmap).

Sponsor classification + prep-time/date/resource backfill all live in enrich.py now,
so this file is pure rendering — `tags` and `sreason` arrive ready to display.
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main():
    debriefs = json.loads((BASE / "debriefs.json").read_text())
    details = json.loads((BASE / "post_details.json").read_text())

    # Defensive: if an un-enriched file is built, still show the new vocabulary.
    for d in debriefs:
        d["tags"] = ["Debrief" if t == "Success Story" else t for t in d.get("tags", [])]

    all_resources = sorted(set(r for d in debriefs for r in d["resources"]))
    all_sources = sorted(set(d["source"] for d in debriefs))
    dates = [d["date"] for d in debriefs if d.get("date")]
    min_date, max_date = (min(dates), max(dates)) if dates else ("2025-01-01", "2026-12-31")
    n_deb = sum(1 for d in debriefs if "Debrief" in d["tags"])

    js_data = json.dumps([{
        "id": d["post_id"],
        "date": d["date"], "title": d["title"], "total": d["total_score"],
        "q": d["q_score"], "v": d["v_score"], "di": d["di_score"],
        "resources": d["resources"], "strat": d["strategy_items"], "tags": d["tags"],
        "source": d["source"],
        "permalink": d["permalink"].replace("old.reddit.com", "www.reddit.com"),
        "attempts": d["attempts"], "prep_weeks": d["prep_weeks"],
        "gain": d["point_gain"], "start": d["start_score"],
        "sreason": d.get("sreason", ""), "nreplies": d.get("n_replies"),
    } for d in debriefs], ensure_ascii=False)

    tt_js = json.dumps({
        "Debrief": "Author reports achieving this score and shares their prep experience or strategy.",
        "Asking Question": "Author mentions a target score and is asking for advice \\u2014 has not achieved it yet.",
        "Other": "Mentions a 650+ score but doesn\\u0027t clearly fit a debrief or a question.",
        "Maybe Promo": "Possible promotional signals (brand-endorsement framing, vendor rep in comments, or readers questioning if it\\u0027s an ad) \\u2014 open it and judge.",
        "Self Study": "Used only free resources (GMAT Club, GMAT Ninja, Official Guide, Official Mocks) or no named resource at all \\u2014 no paid prep course.",
    })

    # --- score-slider domain: every stop is a real GMAT Focus score (ends in 5) ----
    # Start the slider at the lowest score that actually appears (not a fixed 205) so
    # there's no empty tail. Default the selection to the lowest *debrief* score, since
    # Debriefs is the default view.
    floor5 = lambda x: ((x - 5) // 10) * 10 + 5
    all_scores = [d["total_score"] for d in debriefs if d.get("total_score")]
    deb_scores = [d["total_score"] for d in debriefs if d.get("total_score") and "Debrief" in d["tags"]]
    SDOMAIN_MIN = floor5(min(all_scores)) if all_scores else 205
    SDOMAIN_MAX, SSTEP = 805, 10
    SDEF_MIN = floor5(min(deb_scores)) if deb_scores else SDOMAIN_MIN
    SDEF_MAX = 805

    details_js = json.dumps(details, ensure_ascii=False, separators=(",", ":"))

    html = TEMPLATE.format(
        js_data=js_data, tt_js=tt_js, n_posts=len(debriefs), n_deb=n_deb,
        min_date=min_date, max_date=max_date,
        sources_opts="".join(f"<option>{s}</option>" for s in all_sources),
        res_opts="".join(f"<option>{r}</option>" for r in all_resources),
        smin=SDOMAIN_MIN, smax=SDOMAIN_MAX, sstep=SSTEP,
        sdef_min=SDEF_MIN, sdef_max=SDEF_MAX,
        # injected as values => NOT re-scanned by .format(), so these raw strings
        # can use normal single braces (no doubling needed).
        detail_css=DETAIL_CSS, detail_js=DETAIL_JS, details_js=details_js,
    )
    (BASE / "dashboard_v12.html").write_text(html)
    print(f"dashboard_v12.html written. {len(debriefs)} posts, {n_deb} debriefs, "
          f"{len(details)} detail pages.")


# The template is kept as one big string so the file stays single-purpose: data in,
# HTML out. {{ }} are literal braces; {name} are Python format fields.
TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>GMATDebriefs — what actually works</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#0b1120;--bg2:#0f172a;--card:#1e293b;--text:#e2e8f0;--accent:#38bdf8;--a2:#a78bfa;
  --a3:#34d399;--amber:#f59e0b;--border:#334155;--muted:#94a3b8;--nav:#0d1424}}
*{{margin:0;padding:0;box-sizing:border-box}}
html{{max-width:100%;overflow-x:hidden}}
body{{font-family:Inter,-apple-system,system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.55;
  width:100%;max-width:100%;overflow-x:hidden;overscroll-behavior-x:none}}
a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}

/* ---- top nav ---- */
.nav{{position:sticky;top:0;z-index:60;background:rgba(13,20,36,.92);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border);display:flex;align-items:center;gap:1.2rem;padding:.6rem 1.4rem}}
.brand{{display:flex;align-items:center;gap:.55rem;font-weight:800;font-size:1.12rem;letter-spacing:-.02em}}
.brand .mk{{flex:0 0 auto}}
.brand b{{color:var(--accent)}}
.tests{{display:flex;gap:.35rem;margin-left:.4rem}}
.testpill{{font-size:.74rem;font-weight:700;padding:.22rem .6rem;border-radius:999px;border:1px solid var(--border);
  color:var(--muted);background:transparent;white-space:nowrap;line-height:1.2}}
.testpill.on{{background:var(--accent);color:#08111f;border-color:var(--accent)}}
.testpill.soon{{opacity:.5;cursor:not-allowed}}
.navsp{{flex:1}}
.navlink{{font-size:.85rem;color:var(--muted);font-weight:600;padding:.35rem .15rem;cursor:pointer;
  border-bottom:2px solid transparent;white-space:nowrap}}
.navlink.on{{color:var(--text);border-bottom-color:var(--accent)}}
.navlink:hover{{color:var(--text);text-decoration:none}}

.ctn{{max-width:1400px;margin:0 auto;padding:1.1rem 1.2rem 3rem}}
.hero{{padding:.4rem 0 1rem}}
.hero h1{{font-size:1.5rem;font-weight:800;letter-spacing:-.02em}}
.hero p{{color:var(--muted);font-size:.9rem;margin-top:.15rem}}

.sts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:.55rem;margin:.9rem 0}}
.st{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.75rem .8rem;text-align:center}}
.st .n{{font-size:1.45rem;font-weight:800;color:var(--accent)}}.st .l{{color:var(--muted);font-size:.7rem;margin-top:.1rem}}

.gr{{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:1rem;margin-bottom:1rem}}
.full{{grid-template-columns:1fr}}
.cd{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem 1.05rem;transition:border-color .15s}}
.cd:hover{{border-color:#41597f}}
.cd h2{{font-size:.95rem;margin-bottom:.12rem;color:var(--text);font-weight:700}}
.cd .sub{{font-size:.72rem;color:var(--muted);margin-bottom:.7rem;line-height:1.4}}
canvas{{max-height:300px}}.tall canvas{{max-height:400px}}

/* ---- sticky filter toolbar ---- */
.fbar{{position:sticky;top:54px;z-index:50;background:rgba(15,23,42,.96);backdrop-filter:blur(8px);
  border:1px solid var(--border);border-radius:12px;padding:.7rem .85rem;margin:.2rem 0 1rem;
  box-shadow:0 6px 18px rgba(0,0,0,.28)}}
.filter-toggle{{display:none}}
.fbar .frow{{display:flex;flex-wrap:wrap;gap:.7rem .9rem;align-items:end}}
.fld{{display:flex;flex-direction:column;gap:.22rem}}
.fld>span{{color:var(--muted);font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em}}
.seg{{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}}
.seg button{{background:transparent;color:var(--muted);border:none;padding:.32rem .62rem;font-size:.76rem;
  font-weight:700;cursor:pointer}}
.seg button.on{{background:var(--accent);color:#08111f}}
.fbar select{{background:#0b1120;color:var(--text);border:1px solid var(--border);border-radius:7px;
  padding:.34rem .45rem;font-size:.78rem;min-width:118px}}
.fbar input[type=date]{{background:#0b1120;color:var(--text);border:1px solid var(--border);border-radius:7px;
  padding:.3rem .4rem;font-size:.76rem}}
.reset{{background:transparent;color:var(--muted);border:1px solid var(--border);border-radius:7px;
  padding:.36rem .7rem;font-weight:700;font-size:.76rem;cursor:pointer}}
.reset:hover{{color:var(--text);border-color:var(--muted)}}
.hits{{font-size:.74rem;color:var(--accent);font-weight:700;white-space:nowrap}}
.scorectl{{display:flex;align-items:center;gap:.6rem}}

/* dual-handle score slider */
.range{{position:relative;width:188px;height:30px;display:flex;align-items:center}}
.range .track{{position:absolute;left:0;right:0;height:5px;border-radius:4px;background:#0b1120;border:1px solid var(--border)}}
.range .fill{{position:absolute;height:5px;border-radius:4px;background:var(--accent)}}
.range input[type=range]{{position:absolute;left:0;width:100%;margin:0;height:30px;background:transparent;
  -webkit-appearance:none;appearance:none;pointer-events:none;touch-action:none}}
.range input[type=range]::-webkit-slider-thumb{{-webkit-appearance:none;pointer-events:auto;width:15px;height:15px;
  border-radius:50%;background:var(--accent);border:2px solid #08111f;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.5)}}
.range input[type=range]::-moz-range-thumb{{pointer-events:auto;width:15px;height:15px;border-radius:50%;
  background:var(--accent);border:2px solid #08111f;cursor:pointer}}
.rdout{{font-size:.78rem;font-weight:700;font-variant-numeric:tabular-nums;color:var(--text);min-width:96px}}

.nt{{background:#16233a;border-left:3px solid var(--accent);padding:.6rem .75rem;border-radius:0 8px 8px 0;
  margin-bottom:1rem;font-size:.78rem;color:var(--muted)}}
.warn{{background:#2a1f12;border-left:3px solid var(--amber);color:#fde68a}}

table{{width:100%;border-collapse:collapse;font-size:.76rem}}
th,td{{padding:.35rem .5rem;text-align:left;border-bottom:1px solid var(--border)}}
th{{color:var(--accent);font-weight:600;cursor:pointer;user-select:none;white-space:nowrap}}
th:hover{{color:var(--text)}}
.ov{{overflow-x:auto;max-height:540px;overflow-y:auto}}
.tag{{display:inline-block;padding:1px 6px;border-radius:5px;font-size:.64rem;font-weight:700;margin:1px;cursor:help}}
.tag-debrief{{background:#166534;color:#bbf7d0}}.tag-question{{background:#1e3a5f;color:#93c5fd}}
.tag-other{{background:#374151;color:#d1d5db}}
.tag-maybe-promo{{background:#854d0e;color:#fef08a}}.tag-self-study{{background:#1e3a5f;color:#93c5fd}}
.cnt{{color:var(--muted);font-size:.8rem;margin-bottom:.3rem}}
.src{{display:inline-block;padding:1px 5px;border-radius:4px;font-size:.64rem;font-weight:700}}
.src-reddit{{background:#ff4500;color:#fff}}.src-gmat-club{{background:#2563eb;color:#fff}}.src-other{{background:#374151;color:#d1d5db}}

.hm{{border-collapse:collapse;font-size:.74rem;width:100%}}
.hm th{{cursor:default;color:var(--muted);font-weight:600;text-align:center;padding:.3rem .4rem;border-bottom:1px solid var(--border)}}
.hm td{{text-align:center;padding:.3rem .4rem;border:1px solid #0b1120;font-variant-numeric:tabular-nums}}
.hm td.lab{{text-align:left;background:transparent;white-space:nowrap;font-weight:600}}
.hm tr.sec td{{border:none;background:transparent}}
.hm tr.sec td.lab{{padding-top:.7rem;padding-bottom:.25rem;font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid var(--border)}}
.hm td.lab.sub{{padding-left:1.1rem;font-weight:500;cursor:help}}
.hm .dot{{display:inline-block;width:.55rem;height:.55rem;border-radius:50%;margin-right:.45rem;vertical-align:middle}}
.legend{{display:flex;align-items:center;gap:.4rem;font-size:.7rem;color:var(--muted);margin-top:.5rem}}
.legend .sw{{width:18px;height:12px;border-radius:2px}}
.seclbl{{font-size:.78rem;font-weight:700;margin:.2rem 0 .1rem;text-align:center}}
.trio{{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}}
.trio canvas{{max-height:240px}}
@media(max-width:680px){{.trio{{grid-template-columns:1fr}}}}
@media(max-width:600px){{.gr{{grid-template-columns:1fr}}}}
/* on phones the decorative test pills don't fit alongside the brand + nav links */
@media(max-width:720px){{.tests{{display:none}}.nav{{gap:.7rem;padding:.6rem .9rem}}.brand{{font-size:1rem}}}}
@media(max-width:760px){{
  .ctn{{width:100%;max-width:100%;overflow-x:clip;padding:.85rem .75rem 2.5rem}}
  .nav{{min-height:50px;gap:.55rem;padding:.55rem .75rem}}
  .brand{{font-size:1rem;min-width:0}}.brand .mk{{width:24px;height:24px}}
  .navlink{{font-size:.78rem;padding:.28rem .05rem}}
  .hero{{padding:.15rem 0 .65rem}}.hero h1{{font-size:1.22rem;line-height:1.2}}
  .hero p{{font-size:.82rem;line-height:1.45}}
  .nt{{font-size:.72rem;line-height:1.42;padding:.55rem .65rem;margin-bottom:.75rem}}
  .fbar{{top:49px;margin:.1rem -.1rem .8rem;border-radius:10px;padding:.45rem;
    max-height:calc(100dvh - 58px);overflow-y:auto;overscroll-behavior:contain}}
  .filter-toggle{{display:flex;width:100%;align-items:center;gap:.75rem;justify-content:space-between;
    background:#0b1120;color:var(--text);border:1px solid var(--border);border-radius:8px;
    padding:.48rem .6rem;text-align:left;cursor:pointer}}
  .filter-toggle span{{display:flex;flex-direction:column;min-width:0;line-height:1.15}}
  .filter-toggle b{{font-size:.82rem}}.filter-toggle small{{margin-top:.12rem;color:var(--muted);
    font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .filter-toggle strong{{margin-left:auto;color:var(--accent);font-size:.76rem;white-space:nowrap}}
  .filter-toggle i{{width:.55rem;height:.55rem;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);
    transform:rotate(45deg);transition:transform .12s;flex:0 0 auto}}
  .fbar.open .filter-toggle i{{transform:rotate(225deg);margin-top:.25rem}}
  .fbar .frow{{display:none;padding:.65rem .05rem .05rem;gap:.55rem;align-items:stretch}}
  .fbar.open .frow{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
  .fld{{min-width:0}}.ftype,.fscore{{grid-column:1/-1}}
  .freset,.fhits{{grid-column:span 1}}
  .seg{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));width:100%}}
  .seg button{{min-height:38px;padding:.4rem .2rem;font-size:.72rem;white-space:nowrap}}
  .fbar select,.fbar input[type=date]{{width:100%;min-width:0;min-height:38px;font-size:.82rem}}
  .scorectl{{width:100%;gap:.55rem}}
  .range{{width:auto;min-width:0;flex:1;height:44px}}
  .range input[type=range]{{height:44px}}
  .range input[type=range]::-webkit-slider-thumb{{width:24px;height:24px}}
  .range input[type=range]::-moz-range-thumb{{width:24px;height:24px}}
  .rdout{{font-size:.84rem;min-width:76px;text-align:right}}
  .reset{{width:100%;min-height:38px}}.fhits{{align-self:center;justify-content:center}}
  .sts{{grid-template-columns:repeat(2,minmax(0,1fr));gap:.45rem;margin:.75rem 0}}
  .st{{padding:.58rem .4rem;border-radius:8px}}.st .n{{font-size:1.18rem}}.st .l{{font-size:.66rem}}
  .gr{{grid-template-columns:minmax(0,1fr);gap:.75rem;margin-bottom:.75rem}}
  .cd{{min-width:0;overflow:hidden;border-radius:10px;padding:.8rem .75rem}}
  .cd h2{{font-size:.9rem}}.cd .sub{{font-size:.68rem;line-height:1.35}}
  canvas{{max-width:100%}}
  .ov{{max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;overscroll-behavior-x:contain}}
  .ov table{{min-width:760px}}.hm{{min-width:620px}}
  .legend{{overflow-x:auto;white-space:nowrap;padding-bottom:.15rem}}
}}

/* ---- in-tab drill overlay (replaces the v10 new-tab popup) ---- */
#drill{{position:fixed;inset:0;z-index:200;background:var(--bg);overflow-y:auto;display:none}}
#drill.on{{display:block}}
.drlhd{{position:sticky;top:0;background:rgba(13,20,36,.96);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border);padding:.7rem 1.2rem;display:flex;align-items:center;gap:1rem}}
.drlhd .back{{display:inline-flex;align-items:center;gap:.4rem;background:var(--accent);color:#08111f;
  border:none;border-radius:8px;padding:.4rem .8rem;font-weight:800;font-size:.82rem;cursor:pointer}}
.drlhd h2{{font-size:1rem;font-weight:700}}.drlhd .meta{{color:var(--muted);font-size:.8rem}}
.drlbody{{max-width:1200px;margin:0 auto;padding:1.1rem 1.2rem 3rem}}

/* about view */
#view-about{{display:none}}
.about{{max-width:820px;margin:0 auto;padding:1rem 0}}
.about h2{{font-size:1.25rem;margin:1.2rem 0 .4rem}}
.about h3{{font-size:.95rem;color:var(--accent);margin:1rem 0 .3rem}}
.about p,.about li{{color:var(--muted);font-size:.9rem;margin-bottom:.5rem}}
.about ul{{padding-left:1.2rem}}
.about .card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.2rem 1.4rem;margin-top:.6rem}}

#tip{{position:fixed;z-index:9999;left:0;top:0;max-width:300px;background:#0b1220;color:var(--text);
  border:1px solid var(--accent);border-radius:7px;padding:.5rem .65rem;font-size:.74rem;line-height:1.45;
  pointer-events:none;opacity:0;transition:opacity .08s;white-space:pre-line;box-shadow:0 8px 24px rgba(0,0,0,.55)}}
#tip.on{{opacity:1}}
#tip .th{{display:block;color:var(--accent);font-weight:700;margin-bottom:.22rem;font-size:.76rem}}
.hm td[data-tip]{{cursor:pointer}}
{detail_css}
</style></head><body>
<div id="tip" role="tooltip"></div>

<!-- ===== top nav ===== -->
<nav class="nav">
  <div class="brand">
    <svg class="mk" width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="7" fill="#0d1424" stroke="#38bdf8" stroke-width="1.5"/>
      <rect x="8"  y="17" width="3.4" height="7"  rx="1.2" fill="#34d399"/>
      <rect x="14.3" y="12" width="3.4" height="12" rx="1.2" fill="#38bdf8"/>
      <rect x="20.6" y="8"  width="3.4" height="16" rx="1.2" fill="#a78bfa"/>
    </svg>
    <span>GMAT<b>Debriefs</b></span>
  </div>
  <div class="tests" id="tests"></div>
  <div class="navsp"></div>
  <span class="navlink on" id="nav-gmat" onclick="showView('gmat')">Dashboard</span>
  <span class="navlink" id="nav-about" onclick="showView('about')">About Us</span>
</nav>

<!-- ===== GMAT dashboard view ===== -->
<div id="view-gmat" class="ctn">
  <div class="hero">
    <h1>Learn from real GMAT debriefs</h1>
    <p>Hundreds of real test-taker debriefs from r/GMAT and GMAT Club, distilled into one place &mdash;
    the resources, prep time, and section splits behind every score. Filter to people like you and see what worked.</p>
  </div>

  <div class="nt warn"><b>How to read this:</b> charts marked <b>(debriefs)</b> count only people who actually
  <b>achieved</b> the score &mdash; not those still asking how to get there. "With vs without" bars compare the
  median score of people who mentioned a tactic against everyone else. Small samples + keyword matching =
  <b>directional, not proof</b>. Tactics need &ge;4 users to appear.</div>

  <!-- sticky filter toolbar -->
  <div class="fbar" id="filterBar">
    <button class="filter-toggle" id="filterToggle" type="button" onclick="toggleFilters()" aria-expanded="false">
      <span><b>Filters</b><small id="filterSummary">Debriefs | {sdef_min}-{sdef_max}</small></span>
      <strong id="filterCount"></strong><i aria-hidden="true"></i>
    </button>
  <div class="frow">
    <div class="fld ftype"><span>Post type</span>
      <div class="seg" id="segType">
        <button data-v="Debrief" class="on">Debriefs</button>
        <button data-v="Asking Question">Questions</button>
        <button data-v="Other">Other</button>
      </div>
    </div>
    <div class="fld fscore"><span>Score range</span>
      <div class="scorectl">
        <div class="range">
          <div class="track"></div><div class="fill" id="sFill"></div>
          <input type="range" id="sLo" min="{sdef_min}" max="{smax}" step="{sstep}" value="{sdef_min}">
          <input type="range" id="sHi" min="{sdef_min}" max="{smax}" step="{sstep}" value="{sdef_max}">
        </div>
        <span class="rdout" id="sOut">{sdef_min}–{sdef_max}</span>
      </div>
    </div>
    <div class="fld"><span>From</span><input type="date" id="fDF" value="{min_date}"></div>
    <div class="fld"><span>To</span><input type="date" id="fDT" value="{max_date}"></div>
    <div class="fld"><span>Source</span><select id="fSrc"><option value="">All sources</option>{sources_opts}</select></div>
    <div class="fld"><span>Resource</span><select id="fRes"><option value="">Any resource</option>{res_opts}</select></div>
    <div class="fld"><span>Attempts</span><select id="fAtt"><option value="">Any</option><option value="1">1st try</option><option value="2">2 tries</option><option value="3+">3+ tries</option></select></div>
    <div class="fld"><span>Promo</span><select id="fSpon"><option value="">Show all</option><option value="hide">Hide promo</option><option value="any">Promo only</option></select></div>
    <div class="fld"><span>Self Study</span><select id="fSelf"><option value="">Any</option><option value="yes">Self study only</option><option value="no">Paid prep only</option></select></div>
    <div class="fld freset"><span>&nbsp;</span><button class="reset" onclick="resetAll()">Reset</button></div>
    <div class="fld fhits"><span>&nbsp;</span><span class="hits" id="hits"></span></div>
  </div></div>

  <div id="statsRow" class="sts"></div>

  <div class="gr">
    <div class="cd"><h2>Total score distribution</h2><div class="sub">How many posts landed at each score. All posts in the current filter. Click a bar to read them.</div><canvas id="c1"></canvas></div>
    <div class="cd"><h2>Where each tier's weak spot is</h2><div class="sub">Median Q / V / DI for each score band (debriefs). The <b>shortest bar</b> in a band is the section holding that tier back.</div><canvas id="c2"></canvas></div>
  </div>

  <div class="gr">
    <div class="cd"><h2>How big a jump is realistic?</h2><div class="sub">Score improvement (start&rarr;official) reported in debriefs, bucketed. Answers the question everyone asks: how far can I realistically move? Click a bar to read those debriefs.</div><canvas id="cGain"></canvas></div>
    <div class="cd"><h2>Resources used</h2><div class="sub">How often each resource is mentioned by people who hit 650+ (debriefs). Pure popularity. Click to read them.</div><canvas id="cFreq"></canvas></div>
  </div>

  <div class="gr">
    <div class="cd tall"><h2>Prep time vs score change</h2><div class="sub">Each dot is a debrief that reported <b>both</b> weeks studied and a start&rarr;official jump. X = weeks of prep, Y = points gained, color = final score. Dashed line = best-fit trend. Click a dot to open the post.</div><canvas id="c3"></canvas></div>
    <div class="cd"><h2>Does more study time help?</h2><div class="sub">Median achieved score per prep-time bucket (debriefs). Hover for sample size; click to read them.</div><canvas id="c5"></canvas></div>
  </div>

  <div class="gr full">
    <div class="cd"><h2>What score do each section's tactics go with?</h2><div class="sub">Bars = <b>median total score</b> of debriefs that mention each tactic (&ge;4 users), sorted high&rarr;low. The <b>dashed line is the overall median</b> &mdash; a bar to its right means that tactic's users tend to score higher. <b>Correlation, not proof.</b> Click a bar to read those posts.</div>
      <div class="trio">
        <div><div class="seclbl" style="color:#38bdf8">Quant</div><canvas id="c4q"></canvas></div>
        <div><div class="seclbl" style="color:#a78bfa">Verbal</div><canvas id="c4v"></canvas></div>
        <div><div class="seclbl" style="color:#34d399">Data Insights</div><canvas id="c4di"></canvas></div>
      </div>
    </div>
  </div>

  <div class="gr full">
    <div class="cd"><h2>What each score tier actually did</h2><div class="sub">% of debriefs <b>in each band</b> that mentioned the tactic. Read a <b>column</b> top-to-bottom to see one tier's playbook; darker = more common. (Reddit debriefs only — tactic tags aren't extracted for GMAT Club yet.)</div>
      <div class="ov"><div id="heatmap"></div></div>
      <div class="legend"><span>0%</span><span class="sw" style="background:rgba(56,189,248,.08)"></span><span class="sw" style="background:rgba(56,189,248,.4)"></span><span class="sw" style="background:rgba(56,189,248,.75)"></span><span class="sw" style="background:rgba(56,189,248,1)"></span><span>most common</span></div>
    </div>
  </div>

  <div class="cd"><h2>All posts</h2><div class="cnt" id="rc"></div>
    <div class="ov"><table><thead><tr>
      <th onclick="srt(0)">Date &#x25B4;&#x25BE;</th><th onclick="srt(1)">Title</th>
      <th onclick="srt(2)">Score &#x25B4;&#x25BE;</th><th onclick="srt(3)">Q</th><th onclick="srt(4)">V</th><th onclick="srt(5)">DI</th>
      <th onclick="srt(6)">Prep (wk)</th><th onclick="srt(7)">Resources</th><th onclick="srt(8)">Att.</th>
      <th onclick="srt(9)">Source</th><th onclick="srt(10)">Tags</th>
    </tr></thead><tbody id="tb"></tbody></table></div></div>
</div>

<!-- ===== about view ===== -->
<div id="view-about" class="ctn"><div class="about">
  <h1 style="font-size:1.6rem">About GMATDebriefs</h1>
  <p>GMATDebriefs collects real test-takers' debriefs &mdash; the posts where someone who just took the
  exam shares their score split, the resources they used, how long they studied, and what they'd do
  differently &mdash; and turns hundreds of them into charts you can filter and drill into.</p>

  <div class="card">
    <h3>Where the data comes from</h3>
    <ul>
      <li><b>r/GMAT</b> &mdash; debrief and result posts since January 2025.</li>
      <li><b>GMAT Club</b> &mdash; threads from the community's two curated "best debriefs" indexes,
        scraped first post + comments so prep time, dates, and promo signals are read from the full thread.</li>
    </ul>
    <h3>How posts are classified</h3>
    <ul>
      <li><b>Debrief</b> &mdash; the author actually achieved the score and shares their prep.</li>
      <li><b>Asking Question</b> &mdash; the author names a target and is seeking advice.</li>
      <li><b>Other</b> &mdash; mentions a score but isn't a debrief or a question.</li>
      <li><b>Self Study</b> &mdash; used only free resources (GMAT Club, GMAT Ninja, Official Guide, Official Mocks) or no named resource at all.</li>
      <li><b>Maybe Promo</b> &mdash; possible promotional signals; a debrief can be flagged when it reads like vendor copy or readers in the comments question whether it's an ad.</li>
    </ul>
    <h3>Honest limits</h3>
    <ul>
      <li>Samples are small and matching is keyword-based &mdash; treat everything as <b>directional, not proof</b>.</li>
      <li>Tactic-level tags (the heatmap) are extracted for Reddit debriefs only, to keep that view consistent.</li>
    </ul>
  </div>

  <h2>Why "Debriefs"?</h2>
  <p>It's the word the community itself uses. Today the focus is the GMAT; the site is built so other
  exams (GRE, and beyond) can slot in as their own tabs once the GMAT view proves itself.</p>
</div></div>

<!-- ===== drill overlay ===== -->
<div id="drill"><div class="drlhd">
  <button class="back" onclick="closeDrill()">&larr; Back</button>
  <div><h2 id="drlTitle"></h2><div class="meta" id="drlMeta"></div></div>
</div><div class="drlbody"><div class="ov"><table><thead><tr>
  <th>Date</th><th>Title</th><th>Score</th><th>Q</th><th>V</th><th>DI</th><th>Prep</th><th>Resources</th><th>Source</th><th>Tags</th>
</tr></thead><tbody id="drlBody"></tbody></table></div></div></div>

<!-- ===== post detail page (built by JS in openPost) ===== -->
<div id="postpage"></div>

<script>
const D={js_data};
const TT={tt_js};
const DETAIL={details_js};

/* ---- views ---- */
const TESTS=[{{id:'gmat',name:'GMAT',on:true}},{{id:'gre',name:'GRE',soon:true}}];
document.getElementById('tests').innerHTML=TESTS.map(t=>
  `<span class="testpill ${{t.on?'on':''}} ${{t.soon?'soon':''}}" title="${{t.soon?'coming later':'GMAT'}}">${{t.name}}${{t.soon?' · soon':''}}</span>`).join('');
function showView(v){{
  document.getElementById('view-gmat').style.display=v==='gmat'?'block':'none';
  document.getElementById('view-about').style.display=v==='about'?'block':'none';
  document.getElementById('nav-gmat').classList.toggle('on',v==='gmat');
  document.getElementById('nav-about').classList.toggle('on',v==='about');
  window.scrollTo(0,0);
}}

/* ---- floating tooltip (same engine as v10; works on heatmap cells + tag chips) ---- */
const TIP=(function(){{
  const el=document.getElementById('tip');let on=false;
  function show(body,head){{el.textContent='';
    if(head){{const h=document.createElement('span');h.className='th';h.textContent=head;el.appendChild(h);}}
    const b=document.createElement('span');b.textContent=body;el.appendChild(b);el.classList.add('on');on=true;}}
  function hide(){{el.classList.remove('on');on=false;}}
  function move(e){{const pad=14;const r=el.getBoundingClientRect();let x=e.clientX+pad,y=e.clientY+pad;
    if(x+r.width>innerWidth-8)x=e.clientX-r.width-pad;if(y+r.height>innerHeight-8)y=e.clientY-r.height-pad;
    el.style.left=Math.max(6,x)+'px';el.style.top=Math.max(6,y)+'px';}}
  document.addEventListener('mouseover',e=>{{const t=e.target.closest('[data-tip]');
    if(t){{show(t.getAttribute('data-tip'),t.getAttribute('data-tiph'));move(e);}}}});
  document.addEventListener('mousemove',e=>{{if(on)move(e);}});
  document.addEventListener('mouseout',e=>{{const t=e.target.closest('[data-tip]');if(t&&!t.contains(e.relatedTarget))hide();}});
  window.addEventListener('scroll',hide,true);return {{hide}};
}})();
Chart.defaults.color='#94a3b8';Chart.defaults.borderColor='#1f2c44';Chart.defaults.font.family='Inter,system-ui,sans-serif';

/* ---- filter state ---- */
let TYPE='Debrief';
const segType=document.getElementById('segType');
segType.addEventListener('click',e=>{{const b=e.target.closest('button');if(!b)return;
  [...segType.children].forEach(x=>x.classList.toggle('on',x===b));TYPE=b.dataset.v;updateSliderDomain();applyAll();}});
const filterBar=document.getElementById('filterBar'),
      filterToggle=document.getElementById('filterToggle'),
      filterSummary=document.getElementById('filterSummary'),
      filterCount=document.getElementById('filterCount');
function toggleFilters(){{
  const open=filterBar.classList.toggle('open');
  filterToggle.setAttribute('aria-expanded',open?'true':'false');
}}
function filterTypeLabel(){{
  if(TYPE==='Debrief')return'Debriefs';
  if(TYPE==='Asking Question')return'Questions';
  return'Other';
}}
function updateFilterChrome(count){{
  let lo=+sLo.value,hi=+sHi.value;if(lo>hi){{const t=lo;lo=hi;hi=t;}}
  if(filterSummary)filterSummary.textContent=filterTypeLabel()+' | '+lo+'-'+hi;
  if(filterCount)filterCount.textContent=count+' match'+(count===1?'':'es');
}}

/* dual-handle score slider — domain adapts to the active post type */
const sLo=document.getElementById('sLo'),sHi=document.getElementById('sHi'),
      sFill=document.getElementById('sFill'),sOut=document.getElementById('sOut');
const SMAX={smax},SSTEP={sstep};
const floor5=x=>Math.floor((x-5)/10)*10+5;
const TYPE_SMIN={{}};['Debrief','Asking Question','Other'].forEach(t=>{{
  const sc=D.filter(d=>(d.tags||[]).includes(t)).map(d=>d.total).filter(Boolean);
  TYPE_SMIN[t]=sc.length?floor5(Math.min(...sc)):SMAX;
}});
let SMIN=TYPE_SMIN[TYPE]||{smin};
function updateSliderDomain(){{
  const newMin=TYPE_SMIN[TYPE]||{smin};
  SMIN=newMin;sLo.min=newMin;sHi.min=newMin;
  if(+sLo.value<newMin)sLo.value=newMin;
  if(+sHi.value<newMin)sHi.value=newMin;
  syncSlider();
}}
function syncSlider(){{
  let lo=+sLo.value,hi=+sHi.value;
  if(lo>hi){{const t=lo;lo=hi;hi=t;}}
  const a=(lo-SMIN)/(SMAX-SMIN)*100,b=(hi-SMIN)/(SMAX-SMIN)*100;
  sFill.style.left=a+'%';sFill.style.width=(b-a)+'%';
  sOut.textContent=lo+'–'+hi;
  updateFilterChrome(gf().length);
  return [lo,hi];
}}
[sLo,sHi].forEach(s=>s.addEventListener('input',()=>{{syncSlider();applyAll();}}));

['fDF','fDT','fSrc','fRes','fAtt','fSpon','fSelf'].forEach(id=>
  document.getElementById(id).addEventListener('change',applyAll));

function gf(){{
  let lo=+sLo.value,hi=+sHi.value;if(lo>hi){{const t=lo;lo=hi;hi=t;}}
  const df=document.getElementById('fDF').value||'2000-01-01',dt=document.getElementById('fDT').value||'2099-12-31';
  const src=document.getElementById('fSrc').value,res=document.getElementById('fRes').value;
  const att=document.getElementById('fAtt').value,spon=document.getElementById('fSpon').value;
  const isFlagged=d=>(d.tags||[]).some(t=>t==='Maybe Promo');
  const self=document.getElementById('fSelf').value;
  const isSelf=d=>(d.tags||[]).includes('Self Study');
  return D.filter(d=>{{
    if(!(d.tags||[]).includes(TYPE))return false;
    if(d.total<lo||d.total>hi)return false;
    if(d.date<df||d.date>dt)return false;
    if(src&&d.source!==src)return false;
    if(res&&!(d.resources||[]).includes(res))return false;
    if(att==='1'&&d.attempts!==1)return false;
    if(att==='2'&&d.attempts!==2)return false;
    if(att==='3+'&&(!d.attempts||d.attempts<3))return false;
    if(spon==='hide'&&isFlagged(d))return false;
    if(spon==='any'&&!isFlagged(d))return false;
    if(self==='yes'&&!isSelf(d))return false;
    if(self==='no'&&isSelf(d))return false;
    return true;
  }});
}}
const deb=arr=>arr.filter(d=>(d.tags||[]).includes('Debrief'));
const isDeb=()=>TYPE==='Debrief';
function med(a){{if(!a.length)return null;const s=a.slice().sort((x,y)=>x-y);const m=Math.floor(s.length/2);return s.length%2?s[m]:Math.round((s[m-1]+s[m])/2)}}
function tc(t){{if(t==='Debrief')return'tag-debrief';if(t==='Asking Question')return'tag-question';if(t==='Maybe Promo')return'tag-maybe-promo';if(t==='Self Study')return'tag-self-study';return'tag-other'}}
function sc(s){{if(s==='Reddit')return'src-reddit';if(s==='GMAT Club')return'src-gmat-club';return'src-other'}}
function tHTML(tags,sreason){{return(tags||[]).map(t=>{{let tip=TT[t]||t;if(t==='Maybe Promo'&&sreason)tip=tip+'\n— '+sreason;const ti=tip.replace(/"/g,'&quot;');return`<span class="tag ${{tc(t)}}" data-tiph="${{t}}" data-tip="${{ti}}">${{t}}</span>`}}).join('')}}
const BANDS=[['650-689',650,689],['690-719',690,719],['720-749',720,749],['750-805',750,805]];

const GLOSS={{
'Q: DS mastery':'Data Sufficiency mastery — drilling the DS question type until its logic is automatic',
'Q: OG practice':'Practicing with the Official Guide, GMAC’s book of real retired GMAT questions',
'Q: TTP grind':'Grinding through Target Test Prep, a structured self-paced online course (strong for Quant)',
'Q: error log':'Keeping an error log — logging every missed question to find and fix recurring weak spots',
'Q: foundations rebuild':'Rebuilding core math fundamentals before moving on to harder practice',
'Q: timed sets':'Practicing questions in timed batches to build speed under exam-like conditions',
'Q: timing/pacing':'Pacing work — managing the clock so you don’t run out of time in a section',
'V: CR frameworks':'Using structured frameworks to break down Critical Reasoning arguments',
'V: GMAT Ninja':'Studying with GMAT Ninja’s free Verbal YouTube videos (and paid tutoring)',
'V: RC active reading':'Active-reading techniques for Reading Comprehension passages',
'V: verbal course':'Taking a dedicated Verbal-focused prep course',
'DI: DI practice':'General practice on the Data Insights section',
'DI: DS-first':'Doing the Data Sufficiency-style DI questions first',
'DI: MSR drilling':'Drilling Multi-Source Reasoning, the multi-tab DI question type',
'DI: graphics/table':'Practicing Graphics Interpretation and Table Analysis DI questions',
'DI: master Q+V first':'Building Quant and Verbal skills first, since DI draws on both',
'GMAT Club':'GMAT Club — this forum’s free question bank, quizzes, and practice tests',
'GMAT Ninja':'GMAT Ninja — free YouTube Verbal lessons plus paid tutoring',
'GMATWhiz':'GMATWhiz — an adaptive online course and tutoring service',
'Magoosh':'Magoosh — budget-friendly online prep with video lessons and practice',
'Manhattan Prep':'Manhattan Prep — well-known strategy guides and courses',
'Official Guide (OG)':'The Official Guide — GMAC’s book of real retired GMAT questions',
'Official Mocks (mba.com)':'GMAC’s official practice exams from mba.com (the most accurate score predictor)',
'Target Test Prep (TTP)':'Target Test Prep — structured self-paced online course, especially strong for Quant',
'e-GMAT':'e-GMAT — online course popular for Verbal and Data Insights'
}};
function glossLines(k){{const s=GLOSS[k];if(!s)return[];const w=s.split(' ');const out=[];let ln='';
  w.forEach(t=>{{if((ln+' '+t).trim().length>46){{out.push(ln.trim());ln=t}}else ln+=' '+t}});
  if(ln.trim())out.push(ln.trim());return out;}}

/* ---- in-tab drill-down ---- */
function openDrill(title,posts){{
  document.getElementById('drlTitle').textContent=title;
  document.getElementById('drlMeta').textContent=posts.length+' post'+(posts.length===1?'':'s')+' · sorted by score';
  const tb=document.getElementById('drlBody');tb.innerHTML='';
  posts.slice().sort((a,b)=>(b.total||0)-(a.total||0)).forEach(x=>{{
    const t=x.title.length>60?x.title.slice(0,60)+'…':x.title;
    const res=(x.resources||[]).slice(0,3).join(', ')||'—';
    const pw=x.prep_weeks?x.prep_weeks+'w':'—';
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${{x.date}}</td><td><a href="#" onclick="openPost('${{x.id}}');return false">${{t}}</a></td>`+
      `<td><b>${{x.total}}</b></td><td>${{x.q||'—'}}</td><td>${{x.v||'—'}}</td><td>${{x.di||'—'}}</td>`+
      `<td>${{pw}}</td><td style="font-size:.72rem">${{res}}</td><td><span class="src ${{sc(x.source)}}">${{x.source}}</span></td>`+
      `<td>${{tHTML(x.tags,x.sreason)}}</td>`;
    tb.appendChild(tr);
  }});
  document.getElementById('drill').classList.add('on');document.body.style.overflow='hidden';
}}
function closeDrill(){{document.getElementById('drill').classList.remove('on');document.body.style.overflow='';}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeDrill();}});

function addChartClick(chart,filterFn,labelFn){{
  chart.options.onClick=(evt,items)=>{{if(!items.length)return;const idx=items[0].index;
    const label=labelFn?labelFn(idx):chart.data.labels[idx];const posts=filterFn(gf(),idx,label);
    if(posts.length)openDrill(label,posts);}};
  chart.options.onHover=(evt,items)=>{{if(evt.native&&evt.native.target)evt.native.target.style.cursor=items.length?'pointer':'default'}};
  chart.update();
}}

function rSt(d){{
  const ss=isDeb()?d:deb(d),scores=ss.map(x=>x.total);
  const qs=ss.filter(x=>x.q).map(x=>x.q),vs=ss.filter(x=>x.v).map(x=>x.v),dis=ss.filter(x=>x.di).map(x=>x.di);
  const gains=ss.filter(x=>x.gain).map(x=>x.gain);
  const f=v=>v==null?'—':v;
  const lbl=isDeb()?'Debriefs in filter':'Posts in filter';
  document.getElementById('statsRow').innerHTML=`
    <div class="st"><div class="n">${{d.length}}</div><div class="l">${{lbl}}</div></div>
    <div class="st"><div class="n">${{f(med(scores))}}</div><div class="l">Median total</div></div>
    <div class="st"><div class="n">${{f(med(qs))}}</div><div class="l">Median Q</div></div>
    <div class="st"><div class="n">${{f(med(vs))}}</div><div class="l">Median V</div></div>
    <div class="st"><div class="n">${{f(med(dis))}}</div><div class="l">Median DI</div></div>
    <div class="st"><div class="n">${{gains.length?'+'+f(med(gains)):'—'}}</div><div class="l">Median gain</div></div>`;
}}

function rTb(d){{
  const tb=document.getElementById('tb');tb.innerHTML='';
  d.forEach(x=>{{
    const r=(x.resources||[]).slice(0,3).join(', ')||'—';
    const t=x.title.length>48?x.title.slice(0,48)+'…':x.title;
    const pw=x.prep_weeks?x.prep_weeks+'w':'—';
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${{x.date}}</td><td><a href="#" onclick="openPost('${{x.id}}');return false">${{t}}</a></td><td><b>${{x.total}}</b></td><td>${{x.q||'—'}}</td><td>${{x.v||'—'}}</td><td>${{x.di||'—'}}</td><td>${{pw}}</td><td style="font-size:.7rem">${{r}}</td><td>${{x.attempts||'—'}}</td><td><span class="src ${{sc(x.source)}}">${{x.source}}</span></td><td>${{tHTML(x.tags,x.sreason)}}</td>`;
    tb.appendChild(tr);
  }});
  document.getElementById('rc').textContent=`Showing ${{d.length}} of ${{D.length}} posts`;
}}

function tacticChart(id,prefix,pool){{
  const ctx=document.getElementById(id);if(!ctx)return;
  const base=med(pool.map(d=>d.total))||0;
  const keys=new Set();pool.forEach(d=>(d.strat||[]).forEach(s=>{{if(s.startsWith(prefix))keys.add(s)}}));
  let rows=[];keys.forEach(k=>{{const u=pool.filter(d=>(d.strat||[]).includes(k));if(u.length>=4)rows.push({{key:k,n:u.length,um:med(u.map(d=>d.total))}})}});
  rows.sort((a,b)=>b.um-a.um);
  if(!rows.length){{CH[id]=new Chart(ctx,{{type:'bar',data:{{labels:['no tactic with ≥4 users'],datasets:[{{data:[0],backgroundColor:'#334155'}}]}},options:{{indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{enabled:false}}}},scales:{{x:{{display:false}},y:{{ticks:{{color:'#64748b'}}}}}}}}}});return;}}
  const labels=rows.map(r=>`${{r.key.replace(/^[A-Za-z]+:\s*/,'')}} (n=${{r.n}})`);
  const data=rows.map(r=>r.um);
  const colors=rows.map(r=>r.um>=base?'#34d399':'#64748b');
  const lo=Math.min(base,...data)-12,hi=Math.max(base,...data)+12;
  const baseLine={{id:'bl'+id,afterDraw(c){{const xp=c.scales.x.getPixelForValue(base);const a=c.chartArea,g=c.ctx;g.save();g.strokeStyle='#cbd5e1';g.setLineDash([4,3]);g.lineWidth=1;g.beginPath();g.moveTo(xp,a.top);g.lineTo(xp,a.bottom);g.stroke();g.restore();}}}};
  CH[id]=new Chart(ctx,{{type:'bar',data:{{labels,datasets:[{{data,backgroundColor:colors,borderRadius:3}}]}},
    options:{{indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{title:items=>rows[items[0].dataIndex].key,afterBody:items=>glossLines(rows[items[0].dataIndex].key),label:c=>{{const r=rows[c.dataIndex];const dd=r.um-base;return [`Users' median: ${{r.um}}`,`Overall median: ${{base}}  (${{dd>=0?'+':''}}${{dd}})`,`${{r.n}} debriefs used it`]}}}}}}}},
    scales:{{x:{{min:lo,max:hi,title:{{display:true,text:`Median total (baseline ${{base}})`}}}},y:{{ticks:{{font:{{size:10}}}}}}}}}},plugins:[baseLine]}});
  addChartClick(CH[id],(f,i)=>{{const r=rows[i];return deb(f).filter(d=>(d.strat||[]).includes(r.key))}},i=>rows[i].key);
}}

/* Official GMAT Focus Edition percentile rankings (GMAC, Nov 2023) */
const PCT={{655:89.6,665:93.2,675:95.2,685:96.7,695:97.9,705:98.1,715:98.7,725:99.2,735:99.5,745:99.7,755:99.9,765:99.9,775:99.9,785:100,795:100,805:100}};
function pctOf(s){{return PCT[s]||null}}

let CH={{}};
function dC(){{Object.values(CH).forEach(c=>{{try{{c.destroy()}}catch(e){{}}}});CH={{}}}}

function rCh(d){{
  dC();
  const ss=isDeb()?d:deb(d);
  // c1: score distribution with percentile labels
  const bn={{}};d.forEach(x=>{{bn[x.total]=(bn[x.total]||0)+1}});
  const bk=Object.keys(bn).map(Number).sort((a,b)=>a-b);
  const pctLabels=bk.map(s=>{{const p=pctOf(s);return p?s+'\n('+p+'%)':String(s)}});
  CH.c1=new Chart(document.getElementById('c1'),{{type:'bar',data:{{labels:pctLabels,datasets:[{{label:'Count',data:bk.map(k=>bn[k]),backgroundColor:'#38bdf8',borderRadius:5}}]}},options:{{plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{title:items=>{{const s=bk[items[0].dataIndex];const p=pctOf(s);return p?s+' ('+p+'th percentile)':String(s)}},label:c=>'Posts: '+c.raw}}}}}},scales:{{y:{{beginAtZero:true,ticks:{{stepSize:1}}}},x:{{title:{{display:true,text:'Total score (official percentile)'}},ticks:{{font:{{size:10}},maxRotation:45,minRotation:45}}}}}}}}}});
  addChartClick(CH.c1,(f,i)=>f.filter(x=>x.total===bk[i]),i=>{{const s=bk[i];const p=pctOf(s);return 'Score '+s+(p?' ('+p+'%)':'')}});

  // c2: section weak spot by band
  const labels=BANDS.map(b=>b[0]);
  const medBand=fld=>BANDS.map(b=>{{const v=ss.filter(x=>x.total>=b[1]&&x.total<=b[2]&&x[fld]).map(x=>x[fld]);return v.length?med(v):null}});
  CH.c2=new Chart(document.getElementById('c2'),{{type:'bar',data:{{labels,datasets:[
    {{label:'Quant',data:medBand('q'),backgroundColor:'#38bdf8'}},
    {{label:'Verbal',data:medBand('v'),backgroundColor:'#a78bfa'}},
    {{label:'Data Insights',data:medBand('di'),backgroundColor:'#34d399'}}]}},
    options:{{plugins:{{legend:{{display:true,position:'top'}}}},scales:{{y:{{min:74,max:92,title:{{display:true,text:'Median section score'}}}},x:{{title:{{display:true,text:'Total-score band'}}}}}}}}}});
  addChartClick(CH.c2,(f,i)=>{{const b=BANDS[i];return (isDeb()?f:deb(f)).filter(x=>x.total>=b[1]&&x.total<=b[2])}},i=>BANDS[i][0]+' band');

  // cGain: how big a jump is realistic — distribution of start->official point gains
  const GB=[['<50',0,49],['50-99',50,99],['100-149',100,149],['150-199',150,199],['200+',200,999]];
  const gainsD=ss.filter(x=>x.gain).map(x=>x.gain);
  const gcnt=GB.map(b=>gainsD.filter(g=>g>=b[1]&&g<=b[2]).length);
  CH.cGain=new Chart(document.getElementById('cGain'),{{type:'bar',data:{{labels:GB.map(b=>b[0]+' pts'),datasets:[{{data:gcnt,backgroundColor:'#34d399',borderRadius:5}}]}},
    options:{{plugins:{{legend:{{display:false}},title:{{display:gainsD.length>0,text:`${{gainsD.length}} debriefs report a start→official jump`,color:'#94a3b8',font:{{size:11}}}}}},scales:{{y:{{beginAtZero:true,ticks:{{stepSize:1}},title:{{display:true,text:'# debriefs'}}}},x:{{title:{{display:true,text:'Points gained'}}}}}}}}}});
  addChartClick(CH.cGain,(f,i)=>{{const b=GB[i];return (isDeb()?f:deb(f)).filter(x=>x.gain&&x.gain>=b[1]&&x.gain<=b[2])}},i=>GB[i][0]+' point gain');

  // cFreq: resources popularity
  const rc={{}};ss.forEach(x=>(x.resources||[]).forEach(r=>rc[r]=(rc[r]||0)+1));
  const rfreq=Object.entries(rc).sort((a,b)=>b[1]-a[1]).slice(0,12);
  CH.cFreq=new Chart(document.getElementById('cFreq'),{{type:'bar',data:{{labels:rfreq.map(r=>r[0]),datasets:[{{data:rfreq.map(r=>r[1]),backgroundColor:'#f59e0b',borderRadius:4}}]}},options:{{indexAxis:'y',plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{afterBody:items=>glossLines(rfreq[items[0].dataIndex][0])}}}}}},scales:{{x:{{beginAtZero:true,ticks:{{stepSize:1}},title:{{display:true,text:'# debriefs mentioning it'}}}}}}}}}});
  addChartClick(CH.cFreq,(f,i)=>{{const rn=rfreq[i][0];return (isDeb()?f:deb(f)).filter(x=>(x.resources||[]).includes(rn))}},i=>'Uses '+rfreq[i][0]);

  // c3: prep vs gain scatter, colored by final score
  const pg=ss.filter(x=>x.prep_weeks&&x.gain);
  const sCol=v=>v>=750?'#34d399':v>=720?'#38bdf8':v>=690?'#60a5fa':'#a78bfa';
  const pts=pg.map(x=>({{x:x.prep_weeks,y:x.gain,_p:x}}));
  let trend=[];
  if(pts.length>=2){{const n=pts.length,sx=pts.reduce((a,p)=>a+p.x,0),sy=pts.reduce((a,p)=>a+p.y,0);
    const sxx=pts.reduce((a,p)=>a+p.x*p.x,0),sxy=pts.reduce((a,p)=>a+p.x*p.y,0);const den=n*sxx-sx*sx;
    if(den!==0){{const m=(n*sxy-sx*sy)/den,b0=(sy-m*sx)/n;const xs=pts.map(p=>p.x);const x0=Math.min(...xs),x1=Math.max(...xs);trend=[{{x:x0,y:Math.round(m*x0+b0)}},{{x:x1,y:Math.round(m*x1+b0)}}];}}}}
  CH.c3=new Chart(document.getElementById('c3'),{{type:'scatter',data:{{datasets:[
    {{label:'Posts',data:pts,backgroundColor:pts.map(p=>sCol(p._p.total)),pointRadius:5,pointHoverRadius:7}},
    {{label:'Trend',type:'line',data:trend,borderColor:'#f59e0b',borderDash:[6,4],borderWidth:2,pointRadius:0,fill:false}}]}},
    options:{{plugins:{{legend:{{display:false}},title:{{display:true,text:`${{pts.length}} debriefs report both prep time & a score jump`,color:'#94a3b8',font:{{size:11}}}},
      tooltip:{{callbacks:{{label:c=>{{const p=c.raw&&c.raw._p;return p?[p.title.slice(0,52),`${{p.x}}w prep, +${{p.y}} pts (${{p.start||'?'}}→${{p.total}})`]:`${{c.raw.x}}w, +${{c.raw.y}} pts`}}}}}}}},
    scales:{{x:{{beginAtZero:true,title:{{display:true,text:'Weeks of prep'}}}},y:{{beginAtZero:true,title:{{display:true,text:'Points gained (start → official)'}}}}}}}}}});
  CH.c3.options.onClick=(evt,items)=>{{const it=(items||[]).find(i=>i.datasetIndex===0);if(!it)return;const p=CH.c3.data.datasets[0].data[it.index]._p;if(p)openDrill(`Prep ${{p.x}}w / +${{p.y}} pts`,[p]);}};
  CH.c3.options.onHover=(evt,items)=>{{if(evt.native&&evt.native.target)evt.native.target.style.cursor=(items||[]).some(i=>i.datasetIndex===0)?'pointer':'default'}};
  CH.c3.update();

  tacticChart('c4q','Q:',ss);tacticChart('c4v','V:',ss);tacticChart('c4di','DI:',ss);

  // c5: median score by prep bucket
  const TB=[['0-4',0,4],['5-8',5,8],['9-12',9,12],['13-24',13,24],['25+',25,999]];
  const tbS=TB.map(b=>ss.filter(x=>x.prep_weeks&&x.prep_weeks>=b[1]&&x.prep_weeks<=b[2]).map(x=>x.total));
  const tbMed=tbS.map(a=>a.length?med(a):null),tbN=tbS.map(a=>a.length);
  CH.c5=new Chart(document.getElementById('c5'),{{type:'bar',data:{{labels:TB.map(b=>b[0]+'w'),datasets:[{{data:tbMed,backgroundColor:'#a78bfa',borderRadius:5}}]}},
    options:{{plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>[`Median: ${{c.raw}}`,`n=${{tbN[c.dataIndex]}}`]}}}}}},scales:{{y:{{min:640,max:810,title:{{display:true,text:'Median achieved score'}}}},x:{{title:{{display:true,text:'Prep time'}}}}}}}}}});
  addChartClick(CH.c5,(f,i)=>{{const b=TB[i];return (isDeb()?f:deb(f)).filter(x=>x.prep_weeks&&x.prep_weeks>=b[1]&&x.prep_weeks<=b[2])}},i=>TB[i][0]+' weeks prep');

  renderHeatmap(ss);
}}

function renderHeatmap(ss){{
  const bandSS=BANDS.map(b=>ss.filter(x=>x.total>=b[1]&&x.total<=b[2]));
  const bandN=bandSS.map(a=>a.length);
  const cnt={{}};ss.forEach(x=>(x.strat||[]).forEach(k=>cnt[k]=(cnt[k]||0)+1));
  const items=Object.entries(cnt).filter(e=>e[1]>=4).sort((a,b)=>b[1]-a[1]).map(e=>e[0]);
  const SECTIONS=[{{key:'Q:',name:'Quant',color:'#38bdf8'}},{{key:'V:',name:'Verbal',color:'#a78bfa'}},{{key:'DI:',name:'Data Insights',color:'#f59e0b'}},{{key:'',name:'General',color:'#34d399'}}];
  function sectionOf(it){{return SECTIONS.find(s=>s.key&&it.startsWith(s.key))||SECTIONS[SECTIONS.length-1]}}
  function shortLabel(it){{const s=sectionOf(it);return s.key?it.slice(s.key.length).trim():it}}
  let maxPct=0;const grid={{}};
  items.forEach(it=>{{grid[it]=BANDS.map((b,i)=>{{const tot=bandN[i];if(!tot)return null;const u=bandSS[i].filter(x=>(x.strat||[]).includes(it)).length;const p=Math.round(100*u/tot);if(p>maxPct)maxPct=p;return {{p,u,tot}}}})}});
  if(maxPct===0)maxPct=1;
  let h='<table class="hm"><thead><tr><th style="text-align:left">Tactic ↓ &nbsp; Band →</th>';
  BANDS.forEach((b,i)=>h+=`<th>${{b[0]}}<br><span style="font-weight:400">n=${{bandN[i]}}</span></th>`);
  h+='</tr></thead><tbody>';
  if(!items.length){{h+='<tr><td class="lab" colspan="5" style="color:#94a3b8;font-weight:400">Not enough debriefs in this filter (need tactics mentioned by ≥4 posts).</td></tr>'}}
  SECTIONS.forEach(sec=>{{
    const rows=items.filter(it=>sectionOf(it)===sec);if(!rows.length)return;
    h+=`<tr class="sec"><td class="lab" style="color:${{sec.color}}"><span class="dot" style="background:${{sec.color}}"></span>${{sec.name}}</td>`;
    BANDS.forEach(()=>h+='<td></td>');h+='</tr>';
    rows.forEach(it=>{{
      const tip=(GLOSS[it]||'No description available.').replace(/"/g,'&quot;');const head=it.replace(/"/g,'&quot;');
      h+=`<tr><td class="lab sub" style="color:${{sec.color}}" data-tiph="${{head}}" data-tip="${{tip}}">${{shortLabel(it)}}</td>`;
      grid[it].forEach((cell,bi)=>{{
        if(cell===null){{h+=`<td style="background:#0b1120;color:#475569" data-tip="No ${{BANDS[bi][0]}} debriefs in this filter.">—</td>`}}
        else{{const p=cell.p;const a=Math.max(.06,p/maxPct);const col=a>.6?'#0b1120':'#e2e8f0';const band=BANDS[bi][0];
          const tipBody=`${{p}}% of ${{band}} debriefs used this&#10;(${{cell.u}} of ${{cell.tot}} in this band).&#10;Click to read those posts.`;
          const tiph=(shortLabel(it)+' · '+band).replace(/"/g,'&quot;');
          h+=`<td style="background:rgba(56,189,248,${{a.toFixed(2)}});color:${{col}}" data-tiph="${{tiph}}" data-tip="${{tipBody}}" onclick="hmClick('${{it.replace(/'/g,"\\'")}}',${{BANDS[bi][1]}},${{BANDS[bi][2]}})">${{p}}%</td>`}}
      }});
      h+='</tr>';
    }});
  }});
  h+='</tbody></table>';
  document.getElementById('heatmap').innerHTML=h;
}}
function hmClick(strat,lo,hi){{
  const ss=deb(gf());const posts=ss.filter(x=>x.total>=lo&&x.total<=hi&&(x.strat||[]).includes(strat));
  if(posts.length)openDrill(strat+' in '+lo+'-'+hi,posts);
}}

function applyAll(){{
  const f=gf();
  const matchText=f.length+' match'+(f.length===1?'':'es');
  document.getElementById('hits').textContent=matchText;
  updateFilterChrome(f.length);
  try{{rTb(f)}}catch(e){{console.error('table',e)}}
  try{{rSt(f)}}catch(e){{console.error('stats',e)}}
  try{{rCh(f)}}catch(e){{console.error('charts',e)}}
}}
function resetAll(){{
  TYPE='Debrief';[...segType.children].forEach(x=>x.classList.toggle('on',x.dataset.v==='Debrief'));
  updateSliderDomain();sLo.value=SMIN;sHi.value={sdef_max};syncSlider();
  document.getElementById('fDF').value='{min_date}';document.getElementById('fDT').value='{max_date}';
  ['fSrc','fRes','fAtt','fSpon','fSelf'].forEach(id=>document.getElementById(id).value='');
  applyAll();
}}
let sC=-1,sA=true;
function srt(c){{
  if(sC===c)sA=!sA;else{{sC=c;sA=true}}
  const ks=['date','title','total','q','v','di','prep_weeks','resources','attempts','source','tags'];
  const k=ks[c];const f=gf();
  f.sort((a,b)=>{{let va=Array.isArray(a[k])?a[k].join(','):(a[k]??'');let vb=Array.isArray(b[k])?b[k].join(','):(b[k]??'');
    if(typeof va==='number'&&typeof vb==='number')return sA?va-vb:vb-va;
    return sA?String(va).localeCompare(String(vb)):String(vb).localeCompare(String(va));}});
  rTb(f);
}}
syncSlider();applyAll();
{detail_js}
</script></body></html>"""


# =====================================================================
# Detail-page CSS + JS. These are passed to .format() as *values*, so the
# braces below are literal (no doubling) — write plain CSS / JS here.
# =====================================================================
DETAIL_CSS = r"""
/* ===== post detail page ===== */
#postpage{position:fixed;inset:0;z-index:300;background:var(--bg);overflow-y:auto;display:none}
#postpage.on{display:block}
.dhd{position:sticky;top:0;z-index:5;background:rgba(13,20,36,.96);backdrop-filter:blur(8px);
  border-bottom:1px solid var(--border);padding:.7rem 1.1rem;display:flex;align-items:center;gap:.9rem}
.dback{display:inline-flex;align-items:center;gap:.4rem;background:var(--accent);color:#08111f;border:none;
  border-radius:8px;padding:.45rem .85rem;font-weight:800;font-size:.82rem;cursor:pointer;white-space:nowrap}
.dback:hover{filter:brightness(1.08)}
.dhd-t{flex:1;min-width:0}
.dhd-t h2{font-size:1rem;font-weight:700;line-height:1.25;margin-top:.12rem;
  overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.dorig{display:inline-flex;align-items:center;gap:.35rem;background:#16233a;border:1px solid var(--accent);
  color:var(--accent);border-radius:8px;padding:.45rem .8rem;font-weight:700;font-size:.8rem;white-space:nowrap}
.dorig:hover{background:#1c2c46;text-decoration:none}
.dorig-lg{margin-top:1rem;font-size:.88rem;padding:.6rem 1rem}
.dbody{max-width:1080px;margin:0 auto;padding:1.1rem 1.2rem 4rem}
.dsummary{font-size:.98rem;color:var(--text);background:#16233a;border-left:3px solid var(--accent);
  padding:.7rem .9rem;border-radius:0 8px 8px 0;margin-bottom:1rem}
.dsummary b{color:var(--accent)}
.dstats{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:.55rem;margin-bottom:1.1rem}
.dst{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:.6rem .5rem;text-align:center}
.dst .n{font-size:1.25rem;font-weight:800;color:var(--accent)}
.dst .l{color:var(--muted);font-size:.64rem;margin-top:.12rem;text-transform:uppercase;letter-spacing:.03em}
.dgrid2{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem}
@media(max-width:760px){.dgrid2{grid-template-columns:1fr}}
.dcard{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem 1.05rem}
.dcard h3{font-size:.92rem;font-weight:700;margin-bottom:.1rem}
.dsub{font-size:.72rem;color:var(--muted);margin-bottom:.7rem;line-height:1.4}
.dcap{font-size:.68rem;color:var(--muted);margin-top:.5rem;line-height:1.45}
.dcard canvas{max-height:260px}
.dsec-title{font-size:1.05rem;font-weight:800;margin:1.4rem 0 .2rem}
.dsec-titsub{font-size:.74rem;color:var(--muted);margin-bottom:.7rem}
.dsecs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.85rem}
@media(max-width:860px){.dsecs{grid-template-columns:1fr}}
.dsec{background:var(--card);border:1px solid var(--border);border-top:3px solid var(--c,#38bdf8);
  border-radius:10px;padding:.85rem .9rem}
.dsec-h{display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem}
.dsec-name{font-weight:800;font-size:.9rem;color:var(--c)}
.dsec-score{font-variant-numeric:tabular-nums;font-weight:800;font-size:1.05rem;color:var(--c)}
.dchips{display:flex;flex-wrap:wrap;gap:.3rem;margin-bottom:.55rem}
.dchip{font-size:.66rem;font-weight:700;color:var(--text);background:#0b1120;border:1px solid var(--c);
  border-radius:999px;padding:.12rem .5rem}
.dsec-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.45rem}
.dsec-list li{font-size:.8rem;color:#cbd5e1;line-height:1.45;padding-left:.85rem;position:relative}
.dsec-list li:before{content:"";position:absolute;left:0;top:.5rem;width:.32rem;height:.32rem;
  border-radius:50%;background:var(--c)}
.dnone{font-size:.78rem;color:var(--muted);font-style:italic}
.doverall{font-size:.9rem;line-height:1.6;color:#cbd5e1;margin-top:.4rem}
.dquote{margin-top:1.2rem}
.dquote-body{white-space:pre-wrap;font-size:.84rem;line-height:1.6;color:#cbd5e1;background:#0b1120;
  border:1px solid var(--border);border-radius:8px;padding:.9rem 1rem;max-height:380px;overflow-y:auto}
.dreschips{display:flex;flex-wrap:wrap;gap:.4rem}
.dreschip{font-size:.72rem;font-weight:700;color:#fde68a;background:#2a1f12;border:1px solid #b45309;
  border-radius:6px;padding:.2rem .55rem}
"""

DETAIL_JS = r"""
/* ---------- post detail page ---------- */
let PCH = {};
const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtDate(iso){
  const d = new Date(iso + 'T00:00:00');
  return MON[d.getMonth()] + " '" + String(d.getFullYear()).slice(2);
}
function esc(s){ return (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function bandMed(total){
  const b = BANDS.find(x => total>=x[1] && total<=x[2]) || BANDS[BANDS.length-1];
  const pool = D.filter(d => (d.tags||[]).includes('Debrief') && d.total>=b[1] && d.total<=b[2]);
  const m = f => med(pool.filter(d=>d[f]).map(d=>d[f]));
  return { band:b[0], n:pool.length, q:m('q'), v:m('v'), di:m('di') };
}
function secBlock(name, color, score, tactics, sents){
  const chips = (tactics||[]).map(t=>`<span class="dchip">${esc(t)}</span>`).join('');
  const body = (sents && sents.length)
    ? '<ul class="dsec-list">' + sents.map(s=>`<li>${esc(s)}</li>`).join('') + '</ul>'
    : `<p class="dnone">No ${name}-specific notes in this debrief.</p>`;
  return `<div class="dsec" style="--c:${color}">
    <div class="dsec-h"><span class="dsec-name">${name}</span>${score?`<span class="dsec-score">${score}</span>`:''}</div>
    ${chips ? `<div class="dchips">${chips}</div>` : ''}${body}</div>`;
}

function openPost(id){
  const row = D.find(d => d.id === id);
  if(!row) return;
  const wasOn = document.getElementById('postpage').classList.contains('on');
  const det = DETAIL[id] || {};
  const pct = pctOf(row.total);
  const sec = det.sections || {Q:[],V:[],DI:[],General:[]};
  const tac = det.tactics || {Q:[],V:[],DI:[]};

  const bits = [];
  bits.push(`scored <b>${row.total}</b>${pct?` (${pct}th&nbsp;pct)`:''}`);
  if(row.q && row.v && row.di) bits.push(`Q${row.q} · V${row.v} · DI${row.di}`);
  if(row.gain && row.start) bits.push(`up <b>+${row.gain}</b> from ${row.start}`);
  if(row.prep_weeks) bits.push(`${row.prep_weeks} weeks of prep`);
  if(row.attempts) bits.push(`${row.attempts} attempt${row.attempts>1?'s':''}`);

  const stat = (n,l) => `<div class="dst"><div class="n">${n}</div><div class="l">${l}</div></div>`;
  const dash = v => (v==null || v==='') ? '—' : v;
  const stats = [
    stat(row.total + (pct?`<span style="font-size:.6em;color:var(--muted)"> · ${pct}%</span>`:''),'Total'),
    stat(dash(row.q),'Quant'), stat(dash(row.v),'Verbal'), stat(dash(row.di),'Data Insights'),
    stat(row.prep_weeks?row.prep_weeks+'w':'—','Prep'),
    stat(dash(row.attempts),'Attempts'),
    stat(row.gain?'+'+row.gain:'—','Gain'),
    stat(dash(row.nreplies),'Replies'),
  ].join('');

  const resChips = (row.resources && row.resources.length)
    ? `<div class="dreschips">${row.resources.map(r=>`<span class="dreschip" data-tiph="${esc(r)}" data-tip="${esc(GLOSS[r]||'')}">${esc(r)}</span>`).join('')}</div>`
    : `<p class="dnone">No named resource — likely fully self-directed / free materials.</p>`;

  const ovArr = Array.isArray(det.overall) ? det.overall : (det.overall ? [det.overall] : []);
  const genBlock = ovArr.length
    ? `<div class="dcard" style="margin-top:1rem"><h3>Overall approach &amp; mindset</h3>
        <ul class="dsec-list" style="margin-top:.4rem">${ovArr.map(s=>`<li style="--c:#34d399">${esc(s)}</li>`).join('')}</ul></div>`
    : (sec.General && sec.General.length)
      ? `<div class="dcard" style="margin-top:1rem"><h3>Overall approach &amp; mindset</h3>
          <ul class="dsec-list" style="margin-top:.4rem">${sec.General.map(s=>`<li style="--c:#34d399">${esc(s)}</li>`).join('')}</ul></div>`
      : '';

  const srcClass = sc(row.source);
  const origLabel = row.source === 'Reddit' ? 'Reddit' : (row.source==='GMAT Club'?'GMAT Club':row.source);

  document.getElementById('postpage').innerHTML = `
    <div class="dhd">
      <button class="dback" onclick="closeP()">&larr; Back</button>
      <div class="dhd-t"><span class="src ${srcClass}">${esc(row.source)}</span>
        ${tHTML(row.tags,row.sreason)}<h2>${esc(row.title)}</h2></div>
      <a class="dorig" href="${row.permalink}" target="_blank" rel="noopener">Open original &#8599;</a>
    </div>
    <div class="dbody">
      <p class="dsummary">${esc(row.source)} debrief — ${bits.join(' · ')}.${det.overview?` <span style="color:var(--muted)">${esc(det.overview)}</span>`:''}</p>
      <div class="dstats">${stats}</div>
      <div class="dgrid2">
        <div class="dcard"><h3>Score timeline</h3>
          <div class="dsub">Every score the author reported, over time — plus the back-calculated prep start.</div>
          <canvas id="pTimeline"></canvas>
          <p class="dcap"><b>Amber line</b> = prep started${row.prep_weeks?` (${row.prep_weeks}w back from the post)`:' (prep length not stated)'}.
          ◆ = date estimated (spread across the prep window); ● = date the author stated or the official sitting (the post date).
          Scores are as reported and may mix mocks with official sittings.</p>
        </div>
        <div class="dcard"><h3>Section scores vs typical</h3>
          <div class="dsub">This taker's Q / V / DI against the median of debriefs in the same score band.</div>
          <canvas id="pSection"></canvas></div>
      </div>
      <div class="dcard"><h3>Resources used</h3><div class="dsub">What the author named in the debrief.</div>${resChips}</div>
      <h3 class="dsec-title">Strategy by section</h3>
      <div class="dsec-titsub">Key strategies condensed from the post and the author's comment replies. Chips are the tactics tagged for this post.</div>
      <div class="dsecs">
        ${secBlock('Quant', '#38bdf8', row.q, tac.Q, sec.Q)}
        ${secBlock('Verbal', '#a78bfa', row.v, tac.V, sec.V)}
        ${secBlock('Data Insights', '#34d399', row.di, tac.DI, sec.DI)}
      </div>
      ${genBlock}
      <div class="dcard dquote"><h3>In their own words</h3>
        <div class="dsub">The author's full debrief plus their comment replies, verbatim.</div>
        <div class="dquote-body">${esc(det.body || '(No body text was captured for this post — open the original.)')}</div>
        <a class="dorig dorig-lg" href="${row.permalink}" target="_blank" rel="noopener">Read &amp; reply on the original (${esc(origLabel)}) &#8599;</a>
      </div>
    </div>`;

  Object.values(PCH).forEach(c=>{ try{c.destroy()}catch(e){} }); PCH = {};
  renderTimeline(det, row);
  renderSectionChart(row);
  document.getElementById('postpage').classList.add('on');
  document.body.style.overflow = 'hidden';
  document.querySelector('#postpage .dbody').scrollTop = 0;
  // exactly one history entry per open session, always tracking the current post
  if(wasOn) history.replaceState({pp:id}, ''); else history.pushState({pp:id}, '');
}
function doCloseP(){
  const pp = document.getElementById('postpage');
  pp.classList.remove('on'); pp.innerHTML = '';
  Object.values(PCH).forEach(c=>{ try{c.destroy()}catch(e){} }); PCH = {};
  if(!document.getElementById('drill').classList.contains('on')) document.body.style.overflow = '';
}
function closeP(){ if(history.state && history.state.pp){ history.back(); } else { doCloseP(); } }
window.addEventListener('popstate', () => {
  if(document.getElementById('postpage').classList.contains('on')) doCloseP();
});
document.addEventListener('keydown', e => {
  if(e.key==='Escape' && document.getElementById('postpage').classList.contains('on')){
    closeP(); e.stopPropagation();
  }
}, true);

function renderTimeline(det, row){
  const ctx = document.getElementById('pTimeline'); if(!ctx) return;
  const tl = det.timeline || [];
  if(!tl.length){ ctx.closest('.dcard').querySelector('.dsub').textContent='No score data to plot.'; return; }
  const labels = tl.map(p => fmtDate(p.date));
  const data   = tl.map(p => p.kind==='prep' ? null : p.score);
  const colors = tl.map(p => p.final ? '#34d399' : '#38bdf8');
  const styles = tl.map(p => p.est ? 'rectRot' : 'circle');
  const radii  = tl.map(p => p.kind==='prep' ? 0 : (p.final ? 7 : 5));
  const prepIdx = tl.findIndex(p => p.kind==='prep');
  const scores = tl.filter(p => p.score).map(p => p.score);
  const ymin = Math.max(195, Math.min(...scores) - 25);
  const prepPlug = { id:'prepmark', afterDraw(c){
    if(prepIdx < 0) return;
    const x = c.scales.x.getPixelForValue(prepIdx), a = c.chartArea, g = c.ctx;
    g.save(); g.strokeStyle='#f59e0b'; g.setLineDash([5,4]); g.lineWidth=1.5;
    g.beginPath(); g.moveTo(x, a.top); g.lineTo(x, a.bottom); g.stroke();
    g.setLineDash([]); g.fillStyle='#f59e0b'; g.font='bold 10px Inter,sans-serif'; g.textAlign='left';
    g.fillText('▶ prep', x + 4, a.top + 11); g.restore();
  }};
  PCH.tl = new Chart(ctx, {
    type:'line',
    data:{ labels, datasets:[{ data, borderColor:'#38bdf8', backgroundColor:'#38bdf8',
      pointBackgroundColor:colors, pointBorderColor:colors, pointStyle:styles,
      pointRadius:radii, pointHoverRadius:8, tension:.2, spanGaps:false, borderWidth:2 }] },
    options:{ plugins:{ legend:{display:false}, tooltip:{ callbacks:{
        title: items => { const p = tl[items[0].dataIndex]; return fmtDate(p.date) + (p.est?' (date estimated)':''); },
        label: c => { const p = tl[c.dataIndex];
          if(p.kind==='prep') return 'Prep started';
          const out = ['Score: ' + p.score];
          if(p.final && p.q) out.push(`Q${p.q} · V${p.v} · DI${p.di}`);
          const pc = pctOf(p.score); if(pc) out.push(pc + 'th percentile');
          if(p.final) out.push('Official score'); return out; } } } },
      scales:{ y:{ min:ymin, max:810, title:{display:true,text:'GMAT score'} },
               x:{ title:{display:true,text:'Time →'}, ticks:{maxRotation:0,font:{size:10}} } } },
    plugins:[prepPlug]
  });
}

function renderSectionChart(row){
  const ctx = document.getElementById('pSection'); if(!ctx) return;
  if(!(row.q || row.v || row.di)){
    const card = ctx.closest('.dcard');
    card.querySelector('.dsub').textContent = 'The author did not report a Q / V / DI split.';
    ctx.remove(); return;
  }
  const bm = bandMed(row.total);
  PCH.sec = new Chart(ctx, {
    type:'bar',
    data:{ labels:['Quant','Verbal','Data Insights'], datasets:[
      { label:'This taker', data:[row.q,row.v,row.di],
        backgroundColor:['#38bdf8','#a78bfa','#34d399'], borderRadius:4 },
      { label:`Typical ${bm.band} (n=${bm.n})`, data:[bm.q,bm.v,bm.di],
        backgroundColor:'#475569', borderRadius:4 } ] },
    options:{ plugins:{ legend:{display:true,position:'top',labels:{font:{size:10},boxWidth:12}},
        tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${c.raw==null?'—':c.raw}`}} },
      scales:{ y:{ min:60, max:90, title:{display:true,text:'Section score (60–90)'} } } }
  });
}

/* if the page is reloaded while a post was open, the DOM is blank but the
   history entry survives — clear it so the Back button stays consistent. */
if(history.state && history.state.pp){ try{ history.replaceState(null, ''); }catch(e){} }
"""


if __name__ == "__main__":
    main()
