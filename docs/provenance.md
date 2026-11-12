# Sources and preservation

Checked live on 23 October 2026:

- Revised plan: https://www.overleaf.com/project/6abd035913fae5baa946157b. Source preserved under `paper/research-plan/`.
- Assignment: https://canvas.kth.se/courses/63857/assignments/393674. Assigned template https://www.overleaf.com/read/rgdgsnbnrbvz#24102f, preserved under `paper/professor-template-2026/`.
- Formatting: https://canvas.kth.se/courses/63857/pages/templates-and-formatting. Template fonts/sizes required; KTH logo reserved for employees/theses.
- Final assignment: https://canvas.kth.se/courses/63857/assignments/393673. Ten-page main-body limit; cover, references, appendices excluded; at least 11 pt; no contents page.
- New report project: https://www.overleaf.com/project/6adaa2ee04fc36dc7bdb36ac, copied from the assigned template.

The original template has a stray `w` in its section-format command. The adapted preamble removes that typo and preserves intended geometry, font, sizes, spacing, and headings. It also replaces the deprecated `sourcesanspro` package alias with `sourcesans`, retaining the same font family. The author icons and boxed GitHub link follow the plan. No KTH logo was added.

Primary method sources checked during implementation:

- Persistence: https://otexts.com/fpp3/intro.html, with the plan's Hyndman/Athanasopoulos reference.
- Least squares: https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd431.htm.
- Gilbert burst channel: https://www.nokia.com/bell-labs/publications-and-media/publications/capacity-of-a-burst-noise-channel/, DOI 10.1002/j.1538-7305.1960.tb03959.x.
- PythonRobotics candidate: https://atsushisakai.github.io/PythonRobotics/modules/5_path_planning/coverage_path/coverage_path.html. Inspected as context; no code copied, package installed, or reproduction claimed.

The simulator is new study-specific code. Model forms do not calibrate author-selected numerical controls. Existing plan references remain in the draft bibliography; authors still need to read/check every cited paper and its metadata before submission.

GitHub baseline: `fed03ae354ef45f7326f92edb601beeed55d6829`. A fresh checkout preserved the earlier dirty local clone. Proposal files moved under `paper/Proposal/` without content edits.
