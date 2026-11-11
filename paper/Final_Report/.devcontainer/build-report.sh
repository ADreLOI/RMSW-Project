#!/usr/bin/env bash
# Build on the Linux filesystem. Desktop sources are authoritative.
set -euo pipefail
export LC_ALL=C.UTF-8
project=$(cd "$(dirname "$0")/.." && pwd -P)
key=$(printf '%s' "$project" | sha256sum | cut -d' ' -f1)
cache="${XDG_CACHE_HOME:-$HOME/.cache}/ii2202-final-report-latex/$key"
mirror="$cache/src"
out="$project/build"
mkdir -p "$mirror/build" "$out"
exec 9>"$cache/build.lock"
flock 9

# --delete only touches the private mirror. Preserve its incremental build directory.
rsync -rlt --safe-links --delete --modify-window=-1 \
    --exclude=/.git --exclude=/.devcontainer --exclude=/.vscode --exclude=/build \
    "$project/" "$mirror/"
cd "$mirror"
export REPORT_SOURCE="$project" REPORT_MIRROR="$mirror"
remap_paths() { perl -pe 's/\Q$ENV{REPORT_MIRROR}\E/$ENV{REPORT_SOURCE}/g'; }

# Run the usual LuaLaTeX/BibTeX recipe, preserving diagnostics on failure.
result=0
latexmk -lualatex -synctex=1 -interaction=nonstopmode -file-line-error -halt-on-error \
    -outdir=build main.tex 2>&1 | remap_paths || result=$?
if [[ -f build/main.log ]]; then
    remap_paths < build/main.log > "$out/.main.log.next"
    mv -f "$out/.main.log.next" "$out/main.log"
fi
if (( result != 0 )); then exit "$result"; fi

# The viewer uses these paths for dependency discovery and source/PDF navigation.
for ext in aux fls; do
    remap_paths < "build/main.$ext" > "$out/.main.$ext.next"
    mv -f "$out/.main.$ext.next" "$out/main.$ext"
done
gzip -cd build/main.synctex.gz | remap_paths | gzip -c > "$out/.main.synctex.gz.next"
mv -f "$out/.main.synctex.gz.next" "$out/main.synctex.gz"
cp build/main.pdf "$out/.main.pdf.next"
mv -f "$out/.main.pdf.next" "$out/main.pdf"
