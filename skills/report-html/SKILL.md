---
name: report-html
description: Produce a clean, self-contained single-file HTML report artifact (inline CSS, no external assets, print-friendly).
---
# Self-contained HTML report

Use when the deliverable is a report, summary or dashboard-style page that someone will open straight from disk or attach to an email.

## Requirements
- One file, for example `report.html`, saved in the workspace. No external CSS, fonts, scripts or images; inline everything. Charts are inline SVG or small tables, images are `data:` URIs.
- Valid structure: `<!doctype html>`, `<html lang="en">`, `<meta charset="utf-8">`, viewport meta, a meaningful `<title>`.
- Semantic layout: one `<h1>`, then `<section>` blocks with `<h2>`/`<h3>`, `<table>` with `<thead>` for data, `<figure>` with `<figcaption>` for charts.
- Readable defaults: system font stack, max-width about 70ch, line-height 1.5, generous spacing, contrast ratio at least 4.5:1.
- Dark mode and print: add `@media (prefers-color-scheme: dark)` and `@media print` (white background, no shadows, avoid page breaks inside tables and figures).

## Content
1. Title, date, and a one-paragraph summary at the top with the key finding.
2. Body sections in order of importance, numbers right-aligned in tables with units in headers.
3. Sources section: list every `[src:<id>]` cited in the body with its title or location. Facts not supported by data are stated as "not in the data", never filled in.
4. Method or assumptions, short.

## Skeleton
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Report title</title>
<style>
  :root { --fg:#1b1f24; --bg:#fff; --muted:#5b6570; --line:#d8dde3; --accent:#0b5fff; }
  @media (prefers-color-scheme: dark) { :root { --fg:#e6e9ed; --bg:#14171a; --muted:#9aa4af; --line:#2c333a; --accent:#7aa7ff; } }
  body { font:16px/1.5 system-ui, sans-serif; color:var(--fg); background:var(--bg); max-width:70ch; margin:2rem auto; padding:0 1rem; }
  h1,h2,h3 { line-height:1.2; } h2 { border-bottom:1px solid var(--line); padding-bottom:.25rem; }
  table { border-collapse:collapse; width:100%; } th,td { border-bottom:1px solid var(--line); padding:.4rem .6rem; text-align:left; }
  td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
  figure { margin:1.5rem 0; } figcaption { color:var(--muted); font-size:.9rem; }
  @media print { body { background:#fff; color:#000; max-width:none; } table, figure { break-inside:avoid; } }
</style>
</head>
<body>
<h1>Report title</h1>
<p class="muted">Generated YYYY-MM-DD</p>
<section><h2>Summary</h2><p>...</p></section>
</body>
</html>
```

## Checks before finishing
- Open the file text and confirm there is no `http://` or `https://` in any `src`/`href` that loads a resource.
- Confirm the file is under about 2 MB and that every number in it traces to the data or a script in the workspace.
