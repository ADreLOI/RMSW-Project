FROM python:3.12-slim AS base
WORKDIR /lab/code/simulation
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg PYTHONPATH=/lab/code/simulation/src

FROM base AS web
RUN pip install --no-cache-dir "aiohttp>=3.12,<4"
COPY src/usv_sim/__init__.py src/usv_sim/relay.py src/usv_sim/
COPY src/usv_sim/web src/usv_sim/web
ENV LAB_WEB_BIND=0.0.0.0
EXPOSE 8768
CMD ["python", "-m", "usv_sim.relay"]

FROM base AS engine
COPY pyproject.toml README.md ./
COPY src src
RUN pip install --no-cache-dir -e ".[deploy]"
COPY tests tests
COPY scripts scripts
COPY examples examples
COPY results/core results/core
COPY results/extension results/extension
CMD ["python", "-m", "usv_sim.engine"]
