FROM python:3.12-slim AS base
WORKDIR /lab/code
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg

FROM base AS web
RUN pip install --no-cache-dir "aiohttp>=3.12,<4"
COPY webapp/__init__.py webapp/relay.py webapp/
COPY webapp/static webapp/static
ENV LAB_WEB_BIND=0.0.0.0
EXPOSE 8768
CMD ["python", "-m", "webapp.relay"]

FROM base AS engine
COPY pyproject.toml .
COPY webapp webapp
COPY simulator/usv_sim simulator/usv_sim
RUN pip install --no-cache-dir -e ".[deploy]"
COPY simulator/README.md simulator/README.md
COPY simulator/tests simulator/tests
COPY simulator/scripts simulator/scripts
COPY simulator/examples simulator/examples
COPY simulator/results/core simulator/results/core
COPY simulator/results/extension simulator/results/extension
WORKDIR /lab/code/simulator
CMD ["python", "-m", "usv_sim.engine"]
