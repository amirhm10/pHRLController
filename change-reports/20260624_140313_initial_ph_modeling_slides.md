# Initial pH Modeling Slides

## Objective

Start the slide deck for the pH modeling work using the same Beamer style as the reference CSCHE2026 deck, remove the "Two Suggested Next Parts" section from the presentation-ready report, and place the controller structures from the source document at the end of the slides without changing the document terminology.

## Files Changed

- `reports/ph_modeling_presentation_ready_report.md`
- `reports/presentations/ph_modeling_update_20260624/slides.tex`
- `reports/presentations/ph_modeling_update_20260624/slides.pdf`

## Method Summary

- Inspected the reference deck at:
  `C:\Users\hamed\OneDrive - McMaster University\PythonProjects\Lyapunov_polymer\CSCHE2026\slides.tex`
- Matched the main style cues:
  - Beamer 16:9,
  - Copenhagen theme,
  - maroon structure color,
  - compact rounded blocks,
  - TikZ method diagrams,
  - figure-heavy evidence slides.
- Removed the report section titled `Two Suggested Next Parts`.
- Created a 14-slide Beamer deck with this story:
  1. title,
  2. outline,
  3. Henderson-Hasselbalch baseline,
  4. water as weak steady-state pH input but important dynamic input,
  5. prepared sequential data,
  6. reliable PH_2 / pH-sensor measurement,
  7. HH prediction and bias,
  8. sample-183 residual shift,
  9. apparent pKa calculation,
  10. temperature interpretation check,
  11. raw three-flow control non-uniqueness,
  12. ratio-based controller,
  13. HH baseline + RL correction,
  14. controller structures to carry forward.

## Generated Artifacts

- `reports/presentations/ph_modeling_update_20260624/slides.tex`
- `reports/presentations/ph_modeling_update_20260624/slides.pdf`

## Verification

- Compiled the deck with:
  `pdflatex -interaction=nonstopmode -halt-on-error slides.tex`
- Recompiled once to finalize Beamer navigation and page totals.
- Rendered all 14 PDF pages to PNG for visual inspection.
- Inspected representative pages:
  - Henderson-Hasselbalch baseline slide,
  - data-preparation slide,
  - HH prediction slide,
  - apparent pKa slide,
  - residual-shift slide,
  - temperature-interpretation slide,
  - ratio-based controller slide,
  - HH baseline + RL correction slide,
  - final controller-structure slide.

## Known Limitations

- The deck is an initial slide draft, not yet a final conference-quality version.
- Some source-document equations were reconstructed from Word math object text and repository definitions.
- No new literature citations were independently verified.
- The existing result figures are reused as-is, so some figure labels are smaller than ideal for a final talk.
