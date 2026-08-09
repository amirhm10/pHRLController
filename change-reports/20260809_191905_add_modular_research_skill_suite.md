# Add modular research skill suite

## Objective

Replace the monolithic research-result workflow with a repository-local suite of focused research and engineering skills, while preserving `research-result-loop` as a compatibility router.

## Files changed

- Updated `.agents/skills/research-result-loop/SKILL.md` to route multidisciplinary work to focused specialists.
- Added 20 specialist skill directories under `.agents/skills/`, including their `SKILL.md` files, focused references, and evaluation cases.
- Added `.agents/skills/research-result-loop/evals/evals.json`.
- Removed the superseded `.agents/skills/slide-maker/SKILL.md`.
- Added this change report.

## Method or implementation summary

The skill library now separates research orchestration, evidence and statistics, mathematics, optimization, solver engineering, machine learning, reinforcement learning, control, safety certification, chemical-engineering domains, scientific software, testing, and reproducible reporting. The compatibility skill provides intent-based routing and common evidence rules instead of embedding every workflow in one file.

## Generated artifacts

- 20 focused specialist skill packages.
- 21 total evaluation JSON files across the complete 21-skill suite.
- This change report.

## Verification commands and results

- `git diff --check`: passed with only Git line-ending conversion warnings.
- PowerShell JSON parsing over `.agents/skills/**/evals.json`: 21 files parsed successfully.
- PowerShell skill inventory: 21 skill directories and zero missing `SKILL.md` files.
- PowerShell frontmatter audit: all 21 `SKILL.md` files contain frontmatter markers, `name`, and `description` fields.
- Inventory audit: 104 files and 5,263 lines in the resulting modular skill suite.

## Known limitations or next steps

- The checks validate structure and JSON syntax, not the behavioral quality of every evaluation case.
- The removed slide-specific skill is not replaced by a dedicated presentation-authoring skill in this repository-local suite.
