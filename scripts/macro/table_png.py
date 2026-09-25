#!/usr/bin/env python3
"""Render a Macrobenchmark run as a Markdown table and a PNG.

    python3 scripts/macro/table_png.py results/pixel9/macro/<RUN_TAG> [-o out/basename]

Reads each test's `com.sqlitebenchmark.macro-benchmarkData.json` and reports, per
case, the median across iterations of TraceSectionMetric(Mode.Average) -- the mean
of that iteration's 5 timed samples. Deltas are computed from unrounded values
against NativeScript.

Two totals are printed on purpose, because they are different statistics and the
difference is easy to misread:
  * "Sum of the 17 medians" adds the column exactly as shown.
  * "Suite total" is the median across iterations of each iteration's own sum,
    which is what the run-to-run spread table reports.

PNG rendering shells out to headless Chrome; pass --no-png to skip it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

# Display order and human-readable names, matching RESULTS-PIXEL7.md's table.
CASES = [
    ("schema_create_drop", "Schema create/drop (30 cycles)"),
    ("insert_autocommit", "Autocommit insert (400)"),
    ("insert_transaction", "Transaction insert (400)"),
    ("point_select", "Point select (400)"),
    ("indexed_filter", "Indexed filter (100)"),
    ("range_scan", "Range scan (100)"),
    ("full_scan_aggregate", "Full scan aggregate (40)"),
    ("order_limit", "Order with limit (100)"),
    ("join_aggregate", "Join aggregate (100)"),
    ("like_search", "LIKE search (50)"),
    ("json_extract", "JSON extract (100)"),
    ("update_by_pk", "Update by primary key (400)"),
    ("delete_by_pk", "Delete by primary key (200)"),
    ("upsert", "Upsert (400)"),
    ("transaction_rollback", "Transaction rollback (50)"),
    ("blob_insert_length", "4 KiB BLOB insert and length read (100)"),
    ("index_create", "Index build (2,000 rows)"),
]

# Macrobenchmark test method -> column label. The baseline must come first.
COLUMNS = [
    ("nativescript", "NativeScript"),
    ("reactnative", "React Native"),
    ("nativephpPdo", "NativePHP<br>pdo_sqlite"),
    ("nativephpLaravel", "NativePHP<br>pdo_sqlite via Laravel DB"),
]


def load(run: Path, test: str) -> dict[str, dict]:
    path = run / test / "com.sqlitebenchmark.macro-benchmarkData.json"
    if not path.is_file():
        sys.exit(f"missing {path}")
    benchmarks = json.loads(path.read_text())["benchmarks"]
    if len(benchmarks) != 1:
        sys.exit(f"{path}: expected 1 benchmark, found {len(benchmarks)}")
    metrics = benchmarks[0]["metrics"]
    out: dict[str, dict] = {}
    for key, value in metrics.items():
        m = re.fullmatch(r"case_(.+)_avgAverageMs", key)
        if m:
            out.setdefault(m.group(1), {})["runs"] = value["runs"]
            out[m.group(1)]["median"] = value["median"]
        m = re.fullmatch(r"case_(.+)_countCount", key)
        if m:
            out.setdefault(m.group(1), {})["samples"] = value["median"]
    missing = [c for c, _ in CASES if c not in out]
    if missing:
        sys.exit(f"{path}: missing cases {missing}")
    bad = [c for c, _ in CASES if out[c].get("samples") != 5.0]
    if bad:
        print(f"warning: {test}: cases without 5 captured samples: {bad}", file=sys.stderr)
    out["__startup"] = {"median": metrics.get("timeToInitialDisplayMs", {}).get("median")}
    return out


def plain(label: str) -> str:
    """Column labels carry a <br> for the PNG header; Markdown wants one line."""
    return label.replace("<br>", " ")


def fmt(value: float) -> str:
    return f"{value:,.3f}"


def delta(value: float, base: float) -> str:
    pct = (value / base - 1.0) * 100.0
    return f"{pct:+,.1f}%"


def build(run: Path):
    data = {test: load(run, test) for test, _ in COLUMNS}
    base_test = COLUMNS[0][0]
    rows = []
    for case, label in CASES:
        cells = [data[test][case]["median"] for test, _ in COLUMNS]
        rows.append((label, cells))
    totals_sum = [sum(data[t][c]["median"] for c, _ in CASES) for t, _ in COLUMNS]
    totals_suite = []
    for test, _ in COLUMNS:
        n = len(data[test][CASES[0][0]]["runs"])
        per_iter = [sum(data[test][c]["runs"][i] for c, _ in CASES) for i in range(n)]
        totals_suite.append(statistics.median(per_iter))
    startup = [data[t]["__startup"]["median"] for t, _ in COLUMNS]
    return rows, totals_sum, totals_suite, startup, data[base_test]


def markdown(rows, totals_sum, totals_suite, startup) -> str:
    head = "| Case |"
    sep = "| --- |"
    for i, (_, label) in enumerate(COLUMNS):
        head += f" {plain(label)} |" + ("" if i == 0 else " Δ |")
        sep += " ---: |" + ("" if i == 0 else " ---: |")
    lines = [head, sep]

    def row(label, cells, emphasis=False):
        wrap = (lambda s: f"**{s}**") if emphasis else (lambda s: s)
        out = f"| {wrap(label)} |"
        for i, value in enumerate(cells):
            out += f" {wrap(fmt(value))} |"
            if i:
                out += f" {wrap(delta(value, cells[0]))} |"
        return out

    for label, cells in rows:
        lines.append(row(label, cells))
    lines.append(row("Sum of the 17 medians", totals_sum, emphasis=True))
    lines.append(row("Suite total (median of per-iteration sums)", totals_suite, emphasis=True))
    lines.append(row("Cold start timeToInitialDisplay", startup))
    return "\n".join(lines)


HTML = """<!doctype html><meta charset="utf-8"><title>results</title>
<style>
  :root {{
    --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --rule: #e1e0d9; --rule-strong: #c3c2b7; --faster: #006300; --slower: #d03b3b;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--surface); color: var(--ink);
         font: 14px/1.45 -apple-system, "SF Pro Text", Inter, system-ui, sans-serif; }}
  .wrap {{ display: inline-block; padding: 28px 32px 24px; }}
  h1 {{ font-size: 19px; font-weight: 640; margin: 0 0 3px; letter-spacing: -0.01em; }}
  p.sub {{ margin: 0 0 18px; color: var(--ink-2); font-size: 12.5px; max-width: 78ch; }}
  table {{ border-collapse: collapse; font-variant-numeric: tabular-nums; }}
  th, td {{ padding: 6px 12px; white-space: nowrap; }}
  thead th {{ font-size: 12px; font-weight: 640; color: var(--ink-2); text-align: right;
              vertical-align: bottom; padding-bottom: 8px; white-space: normal;
              max-width: 15ch; border-bottom: 1.5px solid var(--rule-strong); }}
  thead th.case, thead th.d {{ max-width: none; }}
  thead th.case {{ text-align: left; }}
  thead th.d {{ color: var(--muted); font-weight: 600; }}
  th.sep, td.sep {{ border-left: 1px solid var(--rule); }}
  td {{ text-align: right; border-bottom: 1px solid var(--rule); }}
  td.case {{ text-align: left; color: var(--ink-2); }}
  tbody tr:nth-child(even) td {{ background: #f6f6f3; }}
  .d-faster {{ color: var(--faster); }}
  .d-slower {{ color: var(--slower); }}
  tr.total td {{ font-weight: 680; color: var(--ink);
                 border-top: 1.5px solid var(--rule-strong); border-bottom: none;
                 background: transparent !important; }}
  tr.total.first td {{ padding-top: 9px; }}
  tr.extra td {{ color: var(--muted); font-style: italic; border-bottom: none;
                 background: transparent !important; }}
  p.foot {{ margin: 16px 0 0; color: var(--muted); font-size: 11.5px; max-width: 86ch; }}
</style>
<div class="wrap">
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
  {table}
  <p class="foot">{foot}</p>
</div>
"""


def html_table(rows, totals_sum, totals_suite, startup) -> str:
    head = '<thead><tr><th class="case">Case</th>'
    for i, (_, label) in enumerate(COLUMNS):
        head += f'<th class="sep">{label}</th>'
        if i:
            head += '<th class="d">Δ</th>'
    head += "</tr></thead>"

    def cells_html(cells):
        out = ""
        for i, value in enumerate(cells):
            out += f'<td class="sep">{fmt(value)}</td>'
            if i:
                pct = (value / cells[0] - 1.0) * 100.0
                tone = "d-slower" if pct > 0 else "d-faster"
                out += f'<td class="{tone}">{delta(value, cells[0])}</td>'
        return out

    body = "<tbody>"
    for label, cells in rows:
        body += f'<tr><td class="case">{label}</td>{cells_html(cells)}</tr>'
    body += "</tbody><tfoot>"
    body += f'<tr class="total first"><td class="case">Sum of the 17 medians</td>{cells_html(totals_sum)}</tr>'
    body += f'<tr class="total"><td class="case">Suite total (median of per-iteration sums)</td>{cells_html(totals_suite)}</tr>'
    body += f'<tr class="extra"><td class="case">Cold start timeToInitialDisplay</td>{cells_html(startup)}</tr>'
    body += "</tfoot>"
    return f"<table>{head}{body}</table>"


def chrome() -> str | None:
    for candidate in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def render_png(html_path: Path, png_path: Path) -> bool:
    """Screenshot the page oversized, then trim the flat background back to the content."""
    binary = chrome()
    if not binary:
        print("warning: no Chrome/Chromium found; skipping PNG", file=sys.stderr)
        return False
    subprocess.run(
        [binary, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=2", "--default-background-color=FFFCFCFB",
         "--window-size=1800,1200", f"--screenshot={png_path.resolve()}",
         html_path.resolve().as_uri()],
        check=True, capture_output=True,
    )
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return True
    with Image.open(png_path) as im:
        im = im.convert("RGB")
        background = Image.new("RGB", im.size, im.getpixel((im.width - 2, im.height - 2)))
        box = ImageChops.difference(im, background).getbbox()
        if box:
            pad = 24  # keep a little breathing room around the trimmed content
            box = (max(box[0] - pad, 0), max(box[1] - pad, 0),
                   min(box[2] + pad, im.width), min(box[3] + pad, im.height))
            im.crop(box).save(png_path)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--title", default="SQLite benchmark — Pixel 9 (Jetpack Macrobenchmark)")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    rows, totals_sum, totals_suite, startup, _ = build(args.run)
    base = Path(args.out) if args.out else args.run / "table"
    base.parent.mkdir(parents=True, exist_ok=True)

    md = markdown(rows, totals_sum, totals_suite, startup)
    base.with_suffix(".md").write_text(md + "\n")
    print(md)

    subtitle = args.subtitle or (
        "Median across iterations of TraceSectionMetric(Mode.Average): the mean of that "
        "iteration's 5 timed samples, after 1 warmup. Lower is faster. Δ is against "
        "NativeScript, from unrounded values."
    )
    foot = (
        "Application-API timings, not SQLite engine timings: NativeScript and React Native await a "
        "promise per SQL call; the NativePHP columns run the suite synchronously inside one PHP "
        "request. SQLite versions differ. Every app ran PRAGMA journal_mode=WAL, synchronous=FULL, "
        "foreign_keys=ON and read the values back."
    )
    html = HTML.format(title=args.title, subtitle=subtitle, foot=foot,
                       table=html_table(rows, totals_sum, totals_suite, startup))
    html_path = base.with_suffix(".html")
    html_path.write_text(html)

    if not args.no_png:
        if render_png(html_path, base.with_suffix(".png")):
            print(f"\nwrote {base.with_suffix('.png')}", file=sys.stderr)
    print(f"wrote {base.with_suffix('.md')} and {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
