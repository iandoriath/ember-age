#!/usr/bin/env python3
"""Render the player-aid markdown into print-styled HTML handouts.

Sources:
  docs/mechanics/dice-results.md   -> player-aids/reading-the-dice.html
  player-aids/pocket-primer.md     -> player-aids/pocket-primer.html

PDFs are produced separately via headless Chromium (see Makefile 'aids' target).
"""
import re
from datetime import date
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent

# reading-the-dice.html is hand-designed in the sheet-style.css system (spend-menu
# focus) and is NOT generated from docs/mechanics/dice-results.md — the full teaching
# version lives in the GM screen's Reference tab instead.
SHEETS = [
    (ROOT / "player-aids/pocket-primer.md", ROOT / "player-aids/pocket-primer.html"),
]

MD = markdown.Markdown(extensions=["tables"])

TPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  @page {{ size: Letter; margin: 14mm 13mm; }}
  :root {{
    --ink:#241d15; --dim:#6b5f50; --ember:#b4501e; --gold:#8a6a1f; --line:#cfc4b2; --wash:#f6f1e7;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ background:#fff; color:var(--ink); font: 10.5pt/1.45 Georgia, "Times New Roman", serif; }}
  .sheet {{ max-width: 7.6in; margin: 0 auto; padding: 24px 18px; }}
  h1 {{ font: 700 20pt/1.15 "Trebuchet MS", Verdana, sans-serif; color: var(--ember);
       letter-spacing: .02em; margin: 0 0 2pt; }}
  h1 + p em, .subtitle {{ color: var(--dim); }}
  h2 {{ font: 700 12.5pt/1.2 "Trebuchet MS", Verdana, sans-serif; color: var(--ink);
       border-bottom: 2px solid var(--ember); padding-bottom: 2pt; margin: 12pt 0 5pt;
       break-after: avoid; }}
  h3 {{ font: 700 10.5pt/1.2 "Trebuchet MS", Verdana, sans-serif; color: var(--ember);
       margin: 8pt 0 3pt; break-after: avoid; }}
  p {{ margin: 4pt 0; }}
  ul, ol {{ margin: 4pt 0 4pt 16pt; padding: 0; }}
  li {{ margin: 2pt 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 5pt 0; font-size: 9.5pt;
          break-inside: avoid; }}
  th, td {{ border: 1px solid var(--line); padding: 3pt 6pt; text-align: left; vertical-align: top; }}
  th {{ background: var(--wash); font-family: "Trebuchet MS", Verdana, sans-serif;
       font-size: 8.5pt; text-transform: uppercase; letter-spacing: .05em; color: var(--gold); }}
  tr {{ break-inside: avoid; }}
  blockquote {{ margin: 5pt 0; padding: 4pt 10pt; border-left: 3px solid var(--ember);
              background: var(--wash); font-style: italic; color: var(--dim); }}
  .adm {{ border: 1px solid var(--line); border-left: 4px solid var(--ember); background: var(--wash);
        padding: 5pt 9pt; margin: 6pt 0; break-inside: avoid; }}
  .adm-title {{ font: 700 9.5pt "Trebuchet MS", Verdana, sans-serif; color: var(--ember); margin: 0 0 2pt; }}
  code {{ font: 9pt Consolas, monospace; background: var(--wash); padding: 0 3px; }}
  footer {{ margin-top: 10pt; padding-top: 4pt; border-top: 1px solid var(--line);
          color: var(--dim); font-size: 8pt; font-family: "Trebuchet MS", Verdana, sans-serif; }}
  @media screen {{ body {{ background:#e8e2d6; }} .sheet {{ background:#fff; margin:16px auto;
    box-shadow:0 2px 14px rgba(60,45,25,.25); }} }}
</style>
</head>
<body>
<div class="sheet">
{body}
<footer>The Ember Age — a homebrew FFG Star Wars campaign · player aid · {today}</footer>
</div>
</body>
</html>
"""

ADM_RE = re.compile(r'^!!!\s+(\w+)(?:\s+"([^"]*)")?\s*$')


def preprocess_admonitions(text):
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        m = ADM_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        kind, title = m.group(1).lower(), m.group(2) or m.group(1).capitalize()
        i += 1
        body = []
        while i < len(lines) and (lines[i].startswith("    ") or lines[i].strip() == ""):
            if lines[i].strip() == "" and (i + 1 >= len(lines) or not (lines[i + 1].startswith("    ") or lines[i + 1].strip() == "")):
                break
            body.append(lines[i][4:] if lines[i].startswith("    ") else "")
            i += 1
        MD.reset()
        out.append("")
        out.append(f'<div class="adm adm-{kind}"><p class="adm-title">{title}</p>' + MD.convert("\n".join(body)) + "</div>")
        out.append("")
    return "\n".join(out)


def main():
    for src, dst in SHEETS:
        text = src.read_text(encoding="utf-8")
        title = re.search(r"(?m)^# (.+)$", text).group(1)
        MD.reset()
        html = MD.convert(preprocess_admonitions(text))
        html = re.sub(r'<a href="[^"]*\.md[^"]*"[^>]*>(.*?)</a>', r"\1", html, flags=re.S)
        dst.write_text(TPL.format(title=title, body=html, today=date.today().isoformat()), encoding="utf-8")
        print(f"{dst.name}: {dst.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
