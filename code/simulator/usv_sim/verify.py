"""Verify bundle file integrity and compare deterministic scientific run values."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .evidence import sha256
from .experiment import dump


def scientific(row):
    row = deepcopy(row)
    row.pop("wall_s", None)
    for work in row.get("work", {}).values():
        work.pop("cpu_ns", None)
    return row


def verify(root, reference=None):
    root = Path(root).resolve()
    inventory = json.loads((root / "artifact-sha256.json").read_text(encoding="utf-8"))
    for name, expected in inventory.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Inventory contains an external path")
        if sha256(path) != expected:
            raise ValueError(f"Artifact hash mismatch: {name}")
    report = {"artifact_hashes_verified": len(inventory), "all_artifact_hashes_match": True}
    if reference:
        rows = json.loads((root / "runs.json").read_text(encoding="utf-8"))
        old = json.loads((Path(reference) / "runs.json").read_text(encoding="utf-8"))
        key = lambda r: (r["seed"], r["slowdown"], r["fade_length"], r["policy"])
        index = {key(r): scientific(r) for r in old}
        mismatches = [key(r) for r in rows if scientific(r) != index.get(key(r))]
        report.update(scientific_runs_compared=len(rows), reference_runs=len(old),
                      all_scientific_values_match=not mismatches, differing_run_keys=mismatches,
                      excluded_from_comparison=["wall_s", "work.*.cpu_ns"],
                      note="Reconstructed scientific metrics, including warning events and operation counts, are compared exactly.")
        if mismatches:
            raise ValueError(f"{len(mismatches)} scientific run values differ from reference; first: {mismatches[0]}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, help="Write verification outside the immutable bundle")
    args = parser.parse_args()
    if args.output and args.output.resolve().is_relative_to(args.bundle.resolve()):
        parser.error("Write verification outside the immutable bundle")
    result = verify(args.bundle, args.reference)
    if args.output:
        dump(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
