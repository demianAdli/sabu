FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install service source.
COPY services/jug_lca_buildings /app/services/jug_lca_buildings

RUN python -m pip install --upgrade pip \
    && python -m pip install sabu-chassis==0.1.0 \
    && python -m pip install -e /app/services/jug_lca_buildings \
    && python -m pip install gunicorn

WORKDIR /app/services/jug_lca_buildings

# Keep logs in a predictable mount-friendly location.
ENV LOG_DIR_BASE=/app
# Persist cached emissions results and exported reports in a mountable path.
ENV JUG_LCA_ARTIFACTS_DIR=/app/data/jug_lca_buildings

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
