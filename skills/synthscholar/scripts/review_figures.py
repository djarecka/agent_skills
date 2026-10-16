#!/usr/bin/env python3
"""Draw the review's standard figures from its data, as static SVG.

A review written by people carries a handful of figures, each placed in the
section it supports and discussed in the text. This draws the ones the review's
data can support, and only those — a figure is made when there is enough data
for it to show something, never for decoration:

| id | figure | drawn when | placed in |
| --- | --- | --- | --- |
| ``prisma`` | PRISMA 2020 flow diagram | flow counts exist | results.flow |
| ``years`` | included publications per year | ≥ 3 distinct years | results.overview |
| ``designs`` | study design distribution | ≥ 2 known designs | results.overview |
| ``groups`` | studies per group (the protocol's grouping dimension) | ≥ 2 groups | results.groups |
| ``appraisal`` | appraisal concern per domain (Low / Some / High) | ≥ 3 studies appraised | results.appraisal |
| ``retrieval`` | full-text retrieval of the reports sought, by route | ≥ 2 routes, or any not retrieved | results.flow |

Each figure also gets a manifest entry (``figures.json``): file, caption, the
template section it belongs in, and the numbers it shows (``facts``), so its
interpretation can be written from the data rather than from the picture.
``assemble_manuscript.py`` places the figures and numbers them in order.

Charts follow the dataviz rules: one hue for single-series bars, the reserved
status colours for the three concern levels with a text label on every segment
and in the legend (colour never carries meaning alone), 2 px gaps between
stacked segments, recessive axes, direct value labels, a light print surface.

Usage:
    python review_figures.py out/review.json                 # → out/figures/*.svg + figures.json
    python review_figures.py out/review.json --outdir out/figures --only prisma years

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prisma_flow  # noqa: E402

# Palette — dataviz reference instance, light surface (validated: see SKILL notes)
SURFACE = "#ffffff"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"                   # single-series bars: categorical slot 1
CONCERN = {"Low": "#0ca30c", "Some": "#fab219", "High": "#d03b3b"}   # status: good / warning / critical
FONT = "Helvetica, Arial, sans-serif"
W = 760

ROUTE_LABELS = {
    "pmc_oa": "PubMed Central (OA)", "europe_pmc_oa": "Europe PMC (OA)",
    "unpaywall_pdf": "Unpaywall (OA)", "openalex_pdf": "OpenAlex (OA)",
    "semanticscholar_pdf": "Semantic Scholar (OA)", "biorxiv_pdf": "bioRxiv / medRxiv",
    "ezproxy_pdf": "Institutional access", "zenodo_pdf": "Zenodo (deposited copy)",
    "arxiv_pdf": "arXiv (deposited copy)", "user_supplied_pdf": "Supplied by reviewer",
    "article_store": "Article store", "cache": "Cache",
}


# ─────────────────────────── drawing ────────────────────────────

def _svg(width: int, height: int, body: list[str], title: str) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="{FONT}" font-size="13" fill="{INK}">\n'
            f'<title>{escape(title)}</title>\n<rect width="{width}" height="{height}" fill="{SURFACE}"/>\n'
            + "\n".join(body) + "\n</svg>\n")


def _bar_path(x: float, y: float, w: float, h: float, r: float, end: str) -> str:
    """A bar with 4 px rounding on its data end only, square at the baseline."""
    r = max(0.0, min(r, w / 2, h / 2))
    if end == "top":       # vertical bar, baseline at the bottom
        return (f"M{x},{y + h} L{x},{y + r} Q{x},{y} {x + r},{y} L{x + w - r},{y} "
                f"Q{x + w},{y} {x + w},{y + r} L{x + w},{y + h} Z")
    return (f"M{x},{y} L{x + w - r},{y} Q{x + w},{y} {x + w},{y + r} L{x + w},{y + h - r} "
            f"Q{x + w},{y + h} {x + w - r},{y + h} L{x},{y + h} Z")   # horizontal, data end right


def _nice_max(v: int) -> int:
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if v <= step * 5:
            return max(step, -(-v // step) * step)
    return v


def vertical_bars(labels: list[str], values: list[int], title: str, y_label: str) -> str:
    left, right, top, bottom = 56, 16, 18, 52
    plot_w, plot_h = W - left - right, 280
    height = top + plot_h + bottom
    vmax = _nice_max(max(values) or 1)
    n = len(values)
    slot = plot_w / n
    bw = min(42.0, slot * 0.72)
    body = []
    for t in range(0, 6):                       # recessive grid + y ticks
        v = vmax * t / 5
        y = top + plot_h - plot_h * t / 5
        body.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        body.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" fill="{INK_2}" font-size="11">{int(v) if v == int(v) else round(v, 1)}</text>')
    body.append(f'<text x="14" y="{top + plot_h / 2}" text-anchor="middle" fill="{INK_2}" font-size="11" '
                f'transform="rotate(-90 14 {top + plot_h / 2})">{escape(y_label)}</text>')
    label_every = max(1, -(-n // 16))           # thin the x labels on long series
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = left + slot * i + (slot - bw) / 2
        h = plot_h * v / vmax
        if v:
            body.append(f'<path d="{_bar_path(x, top + plot_h - h, bw, h, 4, "top")}" fill="{SERIES}">'
                        f'<title>{escape(lab)}: {v}</title></path>')
            body.append(f'<text x="{x + bw / 2:.1f}" y="{top + plot_h - h - 5:.1f}" text-anchor="middle" '
                        f'font-size="11" fill="{INK}">{v}</text>')
        if i % label_every == 0:
            body.append(f'<text x="{x + bw / 2:.1f}" y="{top + plot_h + 18}" text-anchor="middle" '
                        f'font-size="11" fill="{INK_2}">{escape(lab)}</text>')
    body.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="{INK_2}" stroke-width="1"/>')
    return _svg(W, height, body, title)


def horizontal_bars(labels: list[str], values: list[int], title: str, x_label: str) -> str:
    labels = [lab if len(lab) <= 38 else lab[:36] + "…" for lab in labels]
    left = 18 + int(max(len(lab) for lab in labels) * 6.6)
    right, top, row = 48, 12, 26
    plot_w = W - left - right
    height = top + row * len(values) + 44
    vmax = _nice_max(max(values) or 1)
    body = []
    for t in range(0, 6):
        x = left + plot_w * t / 5
        body.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + row * len(values)}" stroke="{GRID}" stroke-width="1"/>')
        v = vmax * t / 5
        body.append(f'<text x="{x:.1f}" y="{top + row * len(values) + 16}" text-anchor="middle" fill="{INK_2}" font-size="11">{int(v) if v == int(v) else round(v, 1)}</text>')
    body.append(f'<text x="{left + plot_w / 2}" y="{height - 6}" text-anchor="middle" fill="{INK_2}" font-size="11">{escape(x_label)}</text>')
    for i, (lab, v) in enumerate(zip(labels, values)):
        y = top + row * i + 4
        w = plot_w * v / vmax
        body.append(f'<text x="{left - 8}" y="{y + 13}" text-anchor="end" font-size="12">{escape(lab)}</text>')
        if v:
            body.append(f'<path d="{_bar_path(left, y, w, row - 8, 4, "right")}" fill="{SERIES}"><title>{escape(lab)}: {v}</title></path>')
        body.append(f'<text x="{left + w + 6:.1f}" y="{y + 13}" font-size="11">{v}</text>')
    return _svg(W, height, body, title)


def stacked_concern(domains: list[str], counts: list[dict[str, int]], title: str) -> str:
    domains = [d if len(d) <= 40 else d[:38] + "…" for d in domains]
    left = 18 + int(max(len(d) for d in domains) * 6.6)
    right, top, row = 20, 40, 30
    plot_w = W - left - right
    height = top + row * len(domains) + 30
    body = []
    lx = left                                   # legend: swatch + text label for every level
    for level in ("Low", "Some", "High"):
        body.append(f'<rect x="{lx}" y="10" width="12" height="12" rx="2" fill="{CONCERN[level]}"/>')
        body.append(f'<text x="{lx + 18}" y="20" font-size="12">{level} concern</text>')
        lx += 120
    for i, (dom, c) in enumerate(zip(domains, counts)):
        y = top + row * i
        total = sum(c.values()) or 1
        body.append(f'<text x="{left - 8}" y="{y + 15}" text-anchor="end" font-size="12">{escape(dom)}</text>')
        x = float(left)
        for level in ("Low", "Some", "High"):
            n = c.get(level, 0)
            if not n:
                continue
            w = plot_w * n / total
            seg_w = max(w - 2, 1)               # 2 px surface gap between segments
            body.append(f'<rect x="{x:.1f}" y="{y}" width="{seg_w:.1f}" height="{row - 10}" fill="{CONCERN[level]}">'
                        f'<title>{escape(dom)} — {level}: {n} of {total}</title></rect>')
            if seg_w > 26:                      # direct label: count, and the level's initial
                ink = "#ffffff" if level in ("Low", "High") else INK
                body.append(f'<text x="{x + seg_w / 2:.1f}" y="{y + 15}" text-anchor="middle" font-size="11" '
                            f'fill="{ink}">{n} {level[0]}</text>')
            x += w
    body.append(f'<text x="{left}" y="{height - 6}" fill="{INK_2}" font-size="11">'
                f'Share of appraised studies per domain (n per segment; L / S / H = Low / Some / High concern)</text>')
    return _svg(W, height, body, title)


# ─────────────────────────── data → figures ────────────────────────────

def _year(a: dict) -> int | None:
    m = re.search(r"(19|20)\d\d", str(a.get("year") or ""))
    return int(m.group()) if m else None


def build(review: dict, outdir: Path, only: set[str] | None = None) -> list[dict]:
    outdir.mkdir(parents=True, exist_ok=True)
    arts = review.get("included_articles") or []
    flow = review.get("flow") or {}
    figures: list[dict] = []

    def want(fid: str) -> bool:
        return not only or fid in only

    def emit(fid: str, svg: str, caption: str, section: str, facts: dict) -> None:
        path = (outdir / f"fig_{fid}.svg").resolve()   # absolute: valid from any working directory
        path.write_text(svg, encoding="utf-8")
        figures.append({"id": fid, "file": str(path), "caption": caption, "section": section,
                        "facts": facts})

    if want("prisma") and prisma_flow.load_flow_dict(flow):
        emit("prisma", prisma_flow.render_svg(flow),
             "PRISMA 2020 flow diagram of record identification, screening and inclusion.",
             "results.flow",
             {k: flow.get(k) for k in ("total_identified", "duplicates_removed", "screened_title_abstract",
                                       "excluded_title_abstract", "sought_fulltext", "not_retrieved",
                                       "assessed_eligibility", "excluded_eligibility", "included_synthesis")}
             | {"excluded_reasons": flow.get("excluded_reasons") or {}})

    years = Counter(y for y in (_year(a) for a in arts) if y)
    if want("years") and len(years) >= 3:
        lo, hi = min(years), max(years)
        labels = [str(y) for y in range(lo, hi + 1)]
        values = [years.get(y, 0) for y in range(lo, hi + 1)]
        peak = max(years, key=lambda y: years[y])
        emit("years", vertical_bars(labels, values, "Included publications per year", "Publications"),
             f"Included publications by year of publication ({lo}–{hi}; n = {sum(values)}).",
             "results.overview",
             {"range": [lo, hi], "n": sum(values), "peak_year": peak, "peak_n": years[peak],
              "per_year": dict(zip(labels, values))})

    designs = Counter(((a.get("extracted_data") or {}).get("study_design") or "").strip() for a in arts)
    designs.pop("", None)
    unknown = designs.pop("Unknown", 0)
    if want("designs") and len(designs) >= 2:
        top = designs.most_common(12)
        labels, values = [d for d, _ in top], [n for _, n in top]
        if unknown:
            labels.append("Not reported"); values.append(unknown)
        emit("designs", horizontal_bars(labels, values, "Study designs", "Included studies"),
             f"Study designs of the included studies (n = {sum(values)}).", "results.overview",
             {"designs": dict(zip(labels, values)), "n": sum(values)})

    pga = review.get("per_group_analysis") or {}
    groups = [(str(g.get("label") or ""), int(g.get("n_studies") or 0)) for g in pga.get("groups") or []]
    groups = [g for g in groups if g[0]]
    if want("groups") and len(groups) >= 2:
        groups.sort(key=lambda g: -g[1])
        dim = (pga.get("dimension") or "group").replace("_", " ")
        emit("groups", horizontal_bars([g[0] for g in groups[:15]], [g[1] for g in groups[:15]],
                                       f"Studies per {dim}", "Included studies"),
             f"Included studies per {dim}"
             + (f" (largest 15 of {len(groups)} groups shown)" if len(groups) > 15 else "") + ".",
             "results.groups", {"dimension": dim, "groups": dict(groups),
                                "unlabeled": pga.get("unlabeled_count", 0)})

    appraisals = review.get("structured_appraisal_results") or []
    if not appraisals and isinstance(review.get("prisma_review"), dict):
        appraisals = ((review["prisma_review"].get("methods") or {}).get("critical_appraisal_results")) or []
    per_domain: dict[str, Counter] = {}
    for ap in appraisals:
        for d in ap.get("domains") or []:
            level = d.get("domain_concern")
            if level in CONCERN:
                per_domain.setdefault(d.get("domain_name") or "Domain", Counter())[level] += 1
    if want("appraisal") and len(appraisals) >= 3 and per_domain:
        doms = list(per_domain)
        emit("appraisal", stacked_concern(doms, [dict(per_domain[d]) for d in doms],
                                          "Critical appraisal by domain"),
             f"Critical appraisal concern by domain across {len(appraisals)} appraised studies.",
             "results.appraisal", {"n_appraised": len(appraisals),
                                   "per_domain": {d: dict(per_domain[d]) for d in doms}})

    # Same population as the Methods retrieval table: the reports sought, by the
    # route that retrieved each, plus those not retrieved.
    routes = dict(flow.get("full_text_sources") or {})
    not_retrieved = int(flow.get("not_retrieved") or 0)
    if want("retrieval") and (len(routes) >= 2 or (routes and not_retrieved)):
        items = sorted(routes.items(), key=lambda kv: -kv[1])
        labels = [ROUTE_LABELS.get(k, k) for k, _ in items] + (["Not retrieved"] if not_retrieved else [])
        values = [v for _, v in items] + ([not_retrieved] if not_retrieved else [])
        emit("retrieval", horizontal_bars(labels, values, "Full-text retrieval", "Reports"),
             f"Full-text retrieval of the {sum(values)} reports sought, by route.",
             "results.flow", {"routes": dict(zip(labels, values)),
                              "retrieved": sum(routes.values()), "not_retrieved": not_retrieved})
    return figures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("review", help="review JSON (PRISMAReviewResult)")
    ap.add_argument("--outdir", help="figure directory (default: <review dir>/figures)")
    ap.add_argument("--only", nargs="+", metavar="ID", help="draw only these figure ids")
    args = ap.parse_args()
    src = Path(args.review)
    try:
        review = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"{src}: {e}", file=sys.stderr)
        return 2
    outdir = Path(args.outdir) if args.outdir else src.parent / "figures"
    figs = build(review, outdir, set(args.only) if args.only else None)
    manifest = outdir / "figures.json"
    manifest.write_text(json.dumps({"review": str(src), "figures": figs}, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    for f in figs:
        print(f"  {f['id']:<10} {Path(f['file']).name:<22} → {f['section']}: {f['caption']}")
    print(f"{len(figs)} figure(s); manifest: {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
