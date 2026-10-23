# RMSW Project · II2202

Andrea Lo Iacono and Ettore Mugisha Cirillo. Controlled two-USV coverage under intermittent radio communication.

The revised research plan is implemented. The core evaluation contains 900 runs, five configurations, six conditions, and 30 paired evaluation seeds per condition, following a separate 300-run pilot. All 900 evaluation logs passed metric reconstruction. Results are synthetic evidence; the report remains a working draft for both authors to review.

```text
paper/
  Final_Report/              Active modular final report; main.tex
  research-plan/             Unmodified live Overleaf snapshot, 23 Oct 2026
  professor-template-2026/   Unmodified assigned report template
  Proposal/                 Preserved earlier proposal
code/
  simulation/               Simulator, tests, frozen design, analysis, replay
  docs/                     Provenance and implementation decisions
  data/                     Data notes
```

- [Final-report Overleaf project](https://www.overleaf.com/project/6adaa2ee04fc36dc7bdb36ac)
- [Research-plan Overleaf project](https://www.overleaf.com/project/6abd035913fae5baa946157b)
- [Simulator and reproduction commands](code/simulation/README.md)
- [Results and review limits](code/docs/results-and-review.md)
- [Plan-to-code mapping](code/docs/plan-to-code.md)
- [Sources and preservation](code/docs/provenance.md)

Fixed partitioning completed every evaluation run. Reactive short queues completed none: this no-rendezvous model permits boats to exhaust work beyond radio range. Long queues and predictive variants completed most runs. Trend prediction showed no consistent benefit over an always-long queue or persistence. Do not treat the contrast with the stalled reactive policy as proof of forecast skill or convert operation/byte counts into measured energy savings.

Compile inside `paper/Final_Report/` with LuaLaTeX and BibTeX, using `main.tex`. `II2202-report.tex` is a compatibility wrapper for the original template setting. The assigned font, 11-point body, margins, spacing, and headings are retained; a stray `w` in its section-format command is corrected. GitHub icons and a boxed repository link follow the plan styling. The course forbids the KTH logo on this report.

The original proposal is preserved byte-for-byte at its new location. The existing dirty local clone was untouched. GitHub and Overleaf synchronization is manual; the final-report project contains paper sources and figures only. Coordinate edits, upload the paper package, recompile, and verify the PDF.

Course requirements checked on 23 October 2026: [first draft/template](https://canvas.kth.se/courses/63857/assignments/393674), [formatting](https://canvas.kth.se/courses/63857/pages/templates-and-formatting), [final report](https://canvas.kth.se/courses/63857/assignments/393673). Main body: at most ten pages excluding cover, references, appendices. No course submission has been made.
