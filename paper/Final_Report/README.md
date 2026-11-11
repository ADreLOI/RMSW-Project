# Final report

The entry point is `main.tex`. Compile with LuaLaTeX and BibTeX. The same sources work on Overleaf and in the local Docker environment.

## Local preview in VS Code

1. Start Docker Desktop in Linux container mode. In VS Code with **Dev Containers** installed, open **this folder** (`paper/Final_Report`) as the workspace.
2. Press `Ctrl+Shift+P` and run **Dev Containers: Reopen in Container**. The first time, VS Code builds the image, installs LaTeX Workshop inside the container and compiles `main.tex`. Wait for `build/main.pdf` to appear.
3. Open `main.tex` and press `Ctrl+Alt+V` to view the PDF. Edit a section and press `Ctrl+S` to rebuild and refresh the preview. To trigger a build manually, run **LaTeX Workshop: Build LaTeX project**.

For a build from the container terminal, run `bash .devcontainer/build-report.sh` from this folder. The script caches intermediate files in the container and writes the PDF and SyncTeX data to `build/`. If a build fails, the previous PDF stays available. See `build/main.log` or the **LaTeX Workshop** output for the error.
