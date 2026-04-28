FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the published package only, so the image does not depend on the local
# checkout at runtime.
ARG JUG_LCA_BUILDINGS_VERSION=0.1.0
RUN python -m pip install --upgrade pip \
    && python -m pip install \
        "jug_lca_buildings==${JUG_LCA_BUILDINGS_VERSION}" \
        "sabu-chassis==0.1.0" \
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
