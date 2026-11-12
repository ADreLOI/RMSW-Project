"""Package the active modular report for Overleaf; preserve any existing ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "paper/Final_Report"
FILES = ["main.tex", "II2202-report.tex", "preamble.tex", "frontmatter.tex",
         "references.bib", "myIEEEtran.bst", "DRAFT-NOTES.md"]
FILES += [f"sections/{name}.tex" for name in
          ("01_introduction", "02_method", "03_results", "04_discussion", "05_conclusion", "appendix")]
FILES += [f"generated/{name}" for name in
          ("host-summary.tex", "mission-table.tex", "resource-table.tex", "mission-time.png",
           "resource-tradeoff.png", "primary-contrasts.tex", "complete-contrasts.tex",
           "condition-diagnostics.tex", "policy-diagnostics.tex", "communication-diagnostics.tex",
           "component-diagnostics.tex", "table-provenance.json")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New ZIP path")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; choose a new ZIP name")
    for name in FILES:
        if not (PAPER / name).is_file():
            parser.error(f"Missing report input: {name}")
    manifest = {"entry_point": "main.tex", "compiler": "LuaLaTeX + BibTeX",
                "source_sha256": {name: hashlib.sha256((PAPER / name).read_bytes()).hexdigest() for name in FILES},
                "instructions": "Inspect and back up live Overleaf before uploading. Uploading does not establish compilation or course submission."}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as bundle:
        for name in FILES:
            bundle.write(PAPER / name, name)
        bundle.writestr("report-package.json", json.dumps(manifest, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
