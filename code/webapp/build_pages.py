"""Build public, read-only Pages assets from retained evidence and a verified demo."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit

from webapp import STATIC_DIR
from usv_sim.dashboard import CORE, EXTENSION_EXPORTS, FIGURES, Lab
from usv_sim.evidence import trace
from usv_sim.model import POLICIES
from usv_sim.verify import scientific, verify


def api_key(path):
    url = urlsplit(path)
    query = sorted((k, v) for k, v in parse_qsl(url.query) if (k, v) != ("dataset", "core"))
    return url.path + ("?" + urlencode(query) if query else "")


def build(output, demo_bundle, relay_url=""):
    output, demo_bundle = Path(output), Path(demo_bundle)
    if relay_url:
        url = urlsplit(relay_url)
        if url.scheme != "https" or not url.netloc or url.path not in ("", "/") or url.query or url.fragment or url.username:
            raise ValueError("Relay URL must be an HTTPS origin, without credentials or path")
        relay_url = f"https://{url.netloc}"
    verified = verify(demo_bundle, CORE)
    if not verified.get("all_scientific_values_match") or verified["scientific_runs_compared"] != 5:
        raise ValueError("Publish only the verified five-policy smoke scenario")
    rows = json.loads((demo_bundle / "runs.json").read_text(encoding="utf-8"))
    expected = {(1000, True, 5, p) for p in POLICIES}
    if {(r["seed"], r["slowdown"], r["fade_length"], r["policy"]) for r in rows} != expected:
        raise ValueError("Demo must use seed 1000, slowdown and L=5 for all five policies")
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(STATIC_DIR, output, dirs_exist_ok=True)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "config.js").write_text(
        "window.LAB_CONFIG = " + json.dumps({"static": True, "relayUrl": relay_url}) + ";\n", encoding="utf-8")
    (output / "data").mkdir()
    manifest = {}

    def publish(endpoint, value, name=None):
        content = value if isinstance(value, bytes) else json.dumps(value, separators=(",", ":")).encode()
        suffix = Path(name).suffix if name else ".json"
        relative = "data/" + hashlib.sha256(content).hexdigest() + suffix
        (output / relative).write_bytes(content)
        manifest[api_key(endpoint)] = {"path": relative, "name": name or "data.json"}

    # Isolate the exporter from the operator's job directories and credentials.
    with tempfile.TemporaryDirectory(prefix="rmsw-pages-") as temporary:
        lab = Lab(Path(temporary) / "jobs")
        try:
            catalog = lab.catalog()
            catalog.pop("token")
            catalog["jobs"] = []
            catalog["environment"] = {}
            catalog["available_traces"] = []
            for policy in POLICIES:
                name = f"1000-1-5-{policy}"
                path = demo_bundle / "raw" / f"{name}.jsonl.gz"
                data = trace(path)  # Reconstruct and verify the raw log before export.
                row = next(row for row in rows if row["policy"] == policy)
                # Warning-event lists belong to the summary, not the replay result.
                if scientific(data["result"]) != scientific({k: v for k, v in row.items() if k != "warnings"}):
                    raise ValueError(f"Demo trace does not match its verified summary: {policy}")
                publish(f"/api/trace?run={name}", {**data, "dataset": "core", "name": name})
                publish(f"/api/raw?run={name}", path.read_bytes(), path.name)
                catalog["available_traces"].append(name)
            publish("/api/catalog", catalog)
            publish("/api/jobs", [])
            if catalog["extension_available"]:
                publish("/api/extension", lab.extension_study())
            core_exports = {"runs.json", "frozen-design.json", "condition-summary.csv", "paired-contrasts.csv",
                            "component-resources.csv", "warning-summary.json", "verification.json",
                            "host-benchmark.json", "raw-log-sha256.json", "evaluation-manifest.json", "analysis-manifest.json"}
            for dataset, names in (("core", core_exports), ("extension", EXTENSION_EXPORTS)):
                if dataset == "extension" and not catalog["extension_available"]:
                    continue
                for name in sorted(names):
                    path = lab.download(dataset, name)
                    if path.is_file():
                        publish(f"/api/download?dataset={dataset}&name={name}", path.read_bytes(), name)
            for name in sorted(FIGURES):
                if name.startswith("extension") and not catalog["extension_available"]:
                    continue
                conditional = name.endswith(("condition", "contrasts"))
                if not conditional:
                    data, filename = lab.figure(name)
                    publish(f"/api/figure?name={name}", data, filename)
                for slow in ("true", "false"):
                    for length in ("2", "5", "10"):
                        if conditional:
                            data, filename = lab.figure(name, slow, length)
                        publish(f"/api/figure?name={name}&slowdown={slow}&length={length}", data, filename)
        finally:
            lab.close()
    (output / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "build-info.json").write_text(json.dumps({
        "demo": "Regenerated five-policy smoke scenario; scientific values match retained core evidence.",
        "verification": verified, "public_endpoints": len(manifest),
    }, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory, must not exist")
    parser.add_argument("--demo-bundle", type=Path, required=True)
    parser.add_argument("--relay-url", default="")
    args = parser.parse_args()
    manifest = build(args.output, args.demo_bundle, args.relay_url)
    print(f"Built {len(manifest)} public endpoints in {args.output}")


if __name__ == "__main__":
    main()
