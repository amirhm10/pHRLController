from __future__ import annotations

import base64
import html
import mimetypes
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_MD = ROOT / "reports" / "first_principles_model_validation.md"
OUTPUT_HTML = ROOT / "reports" / "first_principles_model_validation.html"


RESEARCH_PROMPT = """I am working on an inline acetate-buffer pH process. Do not design a controller, MPC, or RL agent yet. The current goal is only to improve the first-principles plant model that predicts the measured outlet pH from the physical inputs.

Use the attached first-principles validation report, its figures, and the lab CSV as the only data evidence. You may search the literature, but use papers only to guide model structure and experiment design. Do not invent new measurements or claim performance beyond this dataset.

Known system:
- Three inlet streams: acetic acid 100 mM, sodium acetate 100 mM, and Arium ultrapure water.
- Logged inputs: acid flow = biosmb-flows[0], acetate flow = biosmb-flows[1], water flow = biosmb-flows[2].
- Reliable measured output: PH_2 only. PH_1 was disconnected and must not be used for metrics.
- Current first-principles chemistry baseline: Henderson-Hasselbalch, pH = pKa + log10(F_acetate / F_acid).
- Existing validation result: the steady-state HH model is correlated with PH_2 but biased and compressed. The current CSV does not uniquely identify physical delay or volume.

Research tasks:
1. Search for literature on acetate-buffer pH modeling, Henderson-Hasselbalch limitations, effective pKa/activity corrections, inline mixing, tubing residence time, static mixer residence-time distribution, and pH electrode response time.
2. Based on the report and literature, propose the next first-principles model structure for y(t) = PH_2(t) from acid, acetate, and water flows.
3. Include explicit equations for flow-to-composition conversion, mixer or tubing volume, transport delay, optional tanks-in-series/first-order mixing, equilibrium or HH chemistry, and pH-sensor lag.
4. Identify which parameters can be fitted from the existing CSV and which cannot be identified without new experiments or geometry metadata.
5. Propose the minimum next open-loop experiment needed to identify effective pKa, pH bias, tubing delay, mixed volume, and sensor response.
6. Give a safe modeling roadmap that uses only this data and the proposed experiment before any controller, MPC, or RL work.

Important constraints:
- Keep the model first-principles and interpretable.
- Do not use PH_1 for validation.
- Do not assume the logged target pH equals the achieved flow ratio.
- Treat time delay, total volume, tubing volume, mixing location, and sensor response as central unknowns.
- Clearly separate what is supported by the current dataset from what requires new lab measurements.
"""


def main() -> None:
    markdown = REPORT_MD.read_text(encoding="utf-8")
    html_body, embedded_images = markdown_to_html(markdown, REPORT_MD.parent)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    page = build_page(html_body, embedded_images, generated_at)
    OUTPUT_HTML.write_text(page, encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML}")
    print(f"Embedded figures: {embedded_images}")


def markdown_to_html(markdown: str, base_dir: Path) -> tuple[str, int]:
    lines = markdown.splitlines()
    blocks: list[str] = []
    embedded_images = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            continue

        if stripped == "$$":
            math_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                math_lines.append(lines[i])
                i += 1
            i += 1
            math_text = html.escape("\n".join(math_lines))
            blocks.append(f'<div class="math-block">\\[\n{math_text}\n\\]</div>')
            continue

        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            alt, url = image_match.groups()
            image_html, was_embedded = image_to_html(alt, url, base_dir)
            embedded_images += int(was_embedded)
            blocks.append(image_html)
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and is_table_rule(lines[i + 1]):
            table_lines = [line]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            blocks.append(table_to_html(table_lines))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2)
            anchor = slugify(text)
            blocks.append(
                f'<h{level} id="{anchor}">{inline_markup(text)}</h{level}>'
            )
            i += 1
            continue

        if stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:])
                i += 1
            blocks.append(
                "<ul>"
                + "".join(f"<li>{inline_markup(item)}</li>" for item in items)
                + "</ul>"
            )
            continue

        numbered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if numbered:
            items = []
            while i < len(lines):
                match = re.match(r"^\d+\.\s+(.+)$", lines[i].strip())
                if not match:
                    break
                items.append(match.group(1))
                i += 1
            blocks.append(
                "<ol>"
                + "".join(f"<li>{inline_markup(item)}</li>" for item in items)
                + "</ol>"
            )
            continue

        paragraph_lines = [stripped]
        i += 1
        while i < len(lines):
            next_stripped = lines[i].strip()
            if not next_stripped or starts_new_block(lines, i):
                break
            paragraph_lines.append(next_stripped)
            i += 1
        blocks.append(f"<p>{inline_markup(' '.join(paragraph_lines))}</p>")

    return "\n".join(blocks), embedded_images


def starts_new_block(lines: list[str], index: int) -> bool:
    stripped = lines[index].strip()
    if stripped.startswith(("```", "$$", "#", "- ", "|", "![")):
        return True
    return re.match(r"^\d+\.\s+", stripped) is not None


def is_table_rule(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?[\s:-]+\|[\s|:-]+\s*", line))


def table_to_html(table_lines: list[str]) -> str:
    headers = split_table_row(table_lines[0])
    rows = [split_table_row(line) for line in table_lines[1:]]
    head = "".join(f"<th>{inline_markup(cell)}</th>" for cell in headers)
    body_rows = []
    for row in rows:
        cells = row + [""] * (len(headers) - len(row))
        body_rows.append(
            "<tr>" + "".join(f"<td>{inline_markup(cell)}</td>" for cell in cells[:len(headers)]) + "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table></div>"
    )


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def image_to_html(alt: str, url: str, base_dir: Path) -> tuple[str, bool]:
    image_path = (base_dir / url).resolve()
    if image_path.exists():
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        source = f"data:{mime_type};base64,{encoded}"
        embedded = True
    else:
        source = url
        embedded = False

    return (
        "<figure>"
        f'<img src="{html.escape(source, quote=True)}" alt="{html.escape(alt, quote=True)}">'
        f"<figcaption>{inline_markup(alt)}</figcaption>"
        "</figure>"
    ), embedded


def inline_markup(text: str) -> str:
    code_spans: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_spans.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00CODE{len(code_spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash_code, text)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    parts: list[str] = []
    last = 0
    for match in link_pattern.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        label, url = match.groups()
        parts.append(
            f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
        )
        last = match.end()
    parts.append(html.escape(text[last:]))
    rendered = "".join(parts)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)

    for index, code_html in enumerate(code_spans):
        rendered = rendered.replace(f"\x00CODE{index}\x00", code_html)
    return rendered


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def build_page(html_body: str, embedded_images: int, generated_at: str) -> str:
    escaped_prompt = html.escape(RESEARCH_PROMPT)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>First-Principles pH Model Validation</title>
  <script>
    window.MathJax = {{
      tex: {{inlineMath: [['$', '$'], ['\\\\(', '\\\\)']]}},
      svg: {{fontCache: 'global'}}
    }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <style>
    :root {{
      --ink: #16302b;
      --muted: #5b6f6b;
      --paper: #fbf6ea;
      --card: #fffdf6;
      --line: #d8cbb3;
      --accent: #0b6b70;
      --accent-2: #b24c32;
      --soft: #e8f1ed;
      --code: #243b3a;
    }}

    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(11, 107, 112, 0.16), transparent 34rem),
        linear-gradient(135deg, #fbf6ea 0%, #eef2e7 52%, #f8eadf 100%);
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.58;
    }}

    .page {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 42px 22px 64px;
    }}

    .hero, .card {{
      background: rgba(255, 253, 246, 0.92);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 22px 60px rgba(45, 31, 18, 0.12);
    }}

    .hero {{
      padding: 34px;
      margin-bottom: 24px;
    }}

    .eyebrow {{
      color: var(--accent-2);
      font-family: "Trebuchet MS", Verdana, sans-serif;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}

    h1, h2, h3, h4 {{
      color: var(--ink);
      line-height: 1.15;
      margin: 1.55em 0 0.55em;
    }}

    h1 {{
      font-size: clamp(2.2rem, 4.8vw, 4.6rem);
      margin-top: 0.18em;
      max-width: 920px;
    }}

    h2 {{
      border-top: 1px solid var(--line);
      padding-top: 1.1em;
      font-size: clamp(1.55rem, 2.6vw, 2.2rem);
    }}

    h3 {{
      color: var(--accent);
      font-size: 1.28rem;
    }}

    a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration-thickness: 0.08em;
    }}

    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 20px;
      color: var(--muted);
      font-family: "Trebuchet MS", Verdana, sans-serif;
      font-size: 0.92rem;
    }}

    .pill {{
      background: var(--soft);
      border: 1px solid #cdded9;
      border-radius: 999px;
      padding: 7px 12px;
    }}

    .card {{
      padding: 26px;
      margin-bottom: 24px;
      overflow: hidden;
    }}

    .prompt textarea {{
      box-sizing: border-box;
      width: 100%;
      min-height: 420px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      color: var(--code);
      background: #fffaf0;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.93rem;
      line-height: 1.5;
    }}

    .prompt button {{
      margin-top: 12px;
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      color: white;
      background: var(--accent);
      font-family: "Trebuchet MS", Verdana, sans-serif;
      font-weight: 700;
      cursor: pointer;
    }}

    .report {{
      padding: 12px 0 0;
    }}

    p, li {{
      font-size: 1.02rem;
    }}

    ul, ol {{
      padding-left: 1.45rem;
    }}

    pre {{
      overflow-x: auto;
      padding: 16px;
      background: #183330;
      color: #fff4dc;
      border-radius: 16px;
    }}

    code {{
      border-radius: 5px;
      padding: 0.12em 0.3em;
      background: #eef1e8;
      color: #7a2d22;
      font-family: Consolas, "Courier New", monospace;
      font-size: 0.92em;
    }}

    pre code {{
      padding: 0;
      background: transparent;
      color: inherit;
    }}

    .math-block {{
      overflow-x: auto;
      margin: 18px 0;
      padding: 14px 18px;
      border-left: 4px solid var(--accent);
      background: #f4f6ec;
      border-radius: 12px;
    }}

    figure {{
      margin: 28px 0;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: #fffaf0;
    }}

    figure img {{
      display: block;
      max-width: 100%;
      height: auto;
      border-radius: 14px;
    }}

    figcaption {{
      margin-top: 10px;
      color: var(--muted);
      font-family: "Trebuchet MS", Verdana, sans-serif;
      font-size: 0.92rem;
    }}

    .table-wrap {{
      overflow-x: auto;
      margin: 18px 0;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fffaf0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 680px;
    }}

    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: #12322e;
      background: #ecf1e6;
      font-family: "Trebuchet MS", Verdana, sans-serif;
      font-size: 0.9rem;
    }}

    tr:last-child td {{
      border-bottom: 0;
    }}

    .footer-note {{
      color: var(--muted);
      font-family: "Trebuchet MS", Verdana, sans-serif;
      font-size: 0.88rem;
      margin-top: 24px;
    }}

    @media (max-width: 720px) {{
      .hero, .card {{
        border-radius: 18px;
        padding: 20px;
      }}

      .page {{
        padding: 24px 12px 48px;
      }}

      table {{
        min-width: 620px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">pH model validation artifact</div>
      <h1>First-Principles pH Model Validation</h1>
      <p>This HTML version is generated from the Markdown report. Figures are embedded directly in the file so it can be shared as a single artifact.</p>
      <div class="meta">
        <span class="pill">Generated: {html.escape(generated_at)}</span>
        <span class="pill">Embedded figures: {embedded_images}</span>
        <span class="pill">Scope: model only, no controller/RL</span>
      </div>
    </section>

    <section class="card prompt">
      <h2 id="copy-ready-research-prompt">Copy-Ready Research Prompt</h2>
      <p>Use this prompt with ChatGPT when searching further. It keeps the next step focused on first-principles modeling from the current data.</p>
      <textarea id="researchPrompt" spellcheck="false">{escaped_prompt}</textarea>
      <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('researchPrompt').value)">Copy prompt</button>
    </section>

    <section class="card">
      <article class="report">
        {html_body}
      </article>
      <p class="footer-note">Generated from {html.escape(str(REPORT_MD.relative_to(ROOT)))}. Do not treat this as a controller result. It is a first-principles model validation artifact.</p>
    </section>
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    main()
