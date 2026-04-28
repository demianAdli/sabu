FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install published packages from PyPI only, so the image does not depend on
# the local checkout at runtime. Leave version args empty to install the latest
# available PyPI releases, or pass build args to pin exact versions.
ARG JUG_LCA_BUILDINGS_VERSION=latest
ARG SABU_CHASSIS_VERSION=latest
RUN set -eux; \
    python -m pip install --upgrade pip; \
    jug_lca_buildings_spec="jug_lca_buildings"; \
    sabu_chassis_spec="sabu-chassis"; \
    if [ "${JUG_LCA_BUILDINGS_VERSION}" != "latest" ]; then \
        jug_lca_buildings_spec="jug_lca_buildings==${JUG_LCA_BUILDINGS_VERSION}"; \
    fi; \
    if [ "${SABU_CHASSIS_VERSION}" != "latest" ]; then \
        sabu_chassis_spec="sabu-chassis==${SABU_CHASSIS_VERSION}"; \
    fi; \
    python -m pip install --upgrade \
        "${jug_lca_buildings_spec}" \
        "${sabu_chassis_spec}" \
        gunicorn

COPY services/jug_lca_buildings/app.py /app/app.py

# Keep logs in a predictable mount-friendly location.
ENV LOG_DIR_BASE=/app
# Persist cached emissions results and exported reports in a mountable path.
ENV JUG_LCA_ARTIFACTS_DIR=/app/data/jug_lca_buildings

# The app listens on 0.0.0.0:5000 inside the container; map any host port you
# want when running it elsewhere, for example `-p 8080:5000`.
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
