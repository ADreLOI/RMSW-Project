FROM debian:bookworm-slim

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      bash ca-certificates git gzip latexmk perl procps rsync util-linux \
      texlive-luatex texlive-latex-extra texlive-fonts-extra \
      texlive-fonts-recommended texlive-bibtex-extra \
      python3 python3-reportlab \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash report
USER report
