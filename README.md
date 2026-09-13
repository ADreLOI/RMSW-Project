# RMSW Project — II2202, Autumn 2026

Andrea Lo Iacono and Ettore Mugisha Cirillo.

Status: proposal preparation. No simulator or experimental results are implemented yet. The scientific direction and research questions remain to be agreed by both authors.

## Where to work

```text
Proposal/II2202-proposal.tex Proposal main document
Proposal/
  preamble.tex              Original course formatting
  frontmatter.tex           Title, authors and template notice
  sections/01-*.tex          Section 1 — Ettore
  sections/02-*.tex          Section 2 — Andrea
  references.tex            Reference section and BibTeX commands
  references.bib            Proposal bibliography, initially empty
  assets/                   Figures used in the report
  appendices/               Optional appendices
  styles/                   BibTeX style
Final_Report/               Final report template and sections
code/docs/                  Drafting worksheet
code/simulation/            Future simulator, configurations and tests
code/data/                  Data provenance; no private or bulk raw data
```

The former zero-byte root files `main.tex` and `preamble.tex` were removed to avoid ambiguous entry points; they remain recoverable in Git history. All section guidance and placeholders were preserved. Existing personal reminders remain in `Cose_Da_Ricordare.txt`.

## Compile and pagination

In Overleaf, choose the document you want to build through **Main document**. Use `Proposal/II2202-proposal.tex` for the proposal. When the final report template is completed, use `Final_Report/main.tex` for the final report. Use **LuaLaTeX**. Compile from the repository root locally too, if a TeX distribution is installed.

Sections use `\input`, not `\include`, which inserts page breaks. Normal page breaks when a page fills remain expected. Fonts, margins, spacing and heading sizes are unchanged. See [Overleaf's explanation](https://www.overleaf.com/learn/latex/Management_in_a_large_project).

## Writing responsibilities

- Ettore: Section 1, Background/Related Work and Research Problem/Aim/Questions.
- Andrea: Section 2, Design, Data/Materials, Procedure and Analysis.
- Both: agree on the question, comparison, scope, evidence and final consistency.

Start with [the Section 2 worksheet](code/docs/section-2-worksheet.md). It contains feedback and author decision prompts, not submission prose. Keep final scientific text student-authored and record AI use as Canvas requires.

The proposal uses BibTeX through `Proposal/references.tex`. Add only sources that were actually read and cited to `Proposal/references.bib`; do not add sample references or unused candidate entries. Before submission, remove visible template guidance if the assignment asks for a clean report.

Before submission: update title/date/period; fill placeholders; remove visible template guidance; verify citations, PDF and applicable AI disclosure. Do not change prescribed formatting to hit a page count.

## Overleaf ↔ GitHub ↔ local clone

Synchronization is **manual**, not automatic publication after every keystroke. Overleaf saves editor changes, but these reach GitHub only through its sync action.

1. Coordinate with your teammate before moving shared files.
2. In Overleaf: Integrations → GitHub → push outstanding Overleaf changes.
3. Locally: check for uncommitted work, then pull GitHub changes (prefer fast-forward-only).
4. Review a focused local change, commit it and push to the linked branch.
5. In Overleaf: Integrations → GitHub → refresh → pull GitHub changes; recompile.
6. If there is a conflict, compare both versions. Do not force-push or overwrite a teammate's changes.

The integration may synchronize code folders too; this organization is not a LaTeX-only sync filter. Keep environments, recordings, bulk outputs and raw datasets outside the tracked tree. If future experiments grow large, consider a separate code/data repository linked by a pinned version.

## Course requirements

- [Course modules](https://canvas.kth.se/courses/63857/modules)
- [Proposal assignment](https://canvas.kth.se/courses/63857/modules/items/1540872)
- [Templates and formatting](https://canvas.kth.se/courses/63857/modules/items/1540850)
- [Generative AI policy](https://canvas.kth.se/courses/63857/modules/items/1540847)

Checked on 11 September 2026. Canvas shows 16 September for the proposal and 1 October for the research plan. Later dates differ between the supplied slides and Canvas; confirm them with the mentor.
