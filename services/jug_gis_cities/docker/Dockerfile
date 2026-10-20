FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install QGIS LTR and the Python runtime needed by PyQGIS.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    python3-pip \
    software-properties-common \
    wget \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/apt/keyrings \
 && wget -O /etc/apt/keyrings/qgis-archive-keyring.gpg \
    https://download.qgis.org/downloads/qgis-archive-keyring.gpg \
 && printf "Types: deb\nURIs: https://qgis.org/ubuntu-ltr\nSuites: jammy\nArchitectures: amd64\nComponents: main\nSigned-By: /etc/apt/keyrings/qgis-archive-keyring.gpg\n" \
    > /etc/apt/sources.list.d/qgis.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    python3-qgis \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

ENV QGIS_PREFIX_PATH=/usr
ENV PYTHONPATH=/usr/share/qgis/python:/usr/share/qgis/python/plugins
ENV QT_QPA_PLATFORM=offscreen
ENV GDAL_DATA=/usr/share/gdal
ENV PROJ_LIB=/usr/share/proj
ENV QGIS_DISABLE_MESSAGE_HOOKS=1
ENV JUG_GIS_CITIES_QGIS_PATH=/usr

# Build-time smoke test: fail the image build if PyQGIS cannot initialize.
RUN python3 -c "import qgis.core as qc; from qgis.core import QgsApplication; QgsApplication.setPrefixPath('/usr', True); app = QgsApplication([], False); app.initQgis(); print('QGIS OK:', qc.Qgis.QGIS_VERSION); app.exitQgis()"

# Copy local sources so development builds can install the current checkout.
COPY libs/sabu_chassis /tmp/build/sabu_chassis
COPY libs/citygisoo /tmp/build/citygisoo
COPY services/jug_gis_cities /tmp/build/jug_gis_cities

# Install from the local checkout for development, or from PyPI for published
# image builds. Leave version args empty to install the latest available PyPI
# releases, or pass build args to pin exact versions.
ARG INSTALL_LOCAL=true
ARG JUG_GIS_CITIES_VERSION=latest
ARG CITYGISOO_VERSION=latest
ARG SABU_CHASSIS_VERSION=latest
RUN set -eux; \
    python3 -m pip install --upgrade pip; \
    if [ "${INSTALL_LOCAL}" = "true" ]; then \
        python3 -m pip install --upgrade \
            /tmp/build/sabu_chassis \
            /tmp/build/citygisoo \
            /tmp/build/jug_gis_cities \
            gunicorn; \
    else \
        jug_gis_cities_spec="jug_gis_cities"; \
        citygisoo_spec="citygisoo"; \
        sabu_chassis_spec="sabu-chassis"; \
        if [ "${JUG_GIS_CITIES_VERSION}" != "latest" ]; then \
            jug_gis_cities_spec="jug_gis_cities==${JUG_GIS_CITIES_VERSION}"; \
        fi; \
        if [ "${CITYGISOO_VERSION}" != "latest" ]; then \
            citygisoo_spec="citygisoo==${CITYGISOO_VERSION}"; \
        fi; \
        if [ "${SABU_CHASSIS_VERSION}" != "latest" ]; then \
            sabu_chassis_spec="sabu-chassis==${SABU_CHASSIS_VERSION}"; \
        fi; \
        python3 -m pip install --upgrade \
            "${jug_gis_cities_spec}" \
            "${citygisoo_spec}" \
            "${sabu_chassis_spec}" \
            gunicorn; \
    fi; \
    rm -rf /tmp/build

COPY services/jug_gis_cities/app.py /app/app.py

# Keep logs in a predictable mount-friendly location.
ENV LOG_DIR_BASE=/app
ENV LOG_FILE_NAME=logs/jug_gis_cities.log
ENV LOG_SERVICE=gis_cities-api
ENV JUG_GIS_CITIES_JOB_STORE_PATH=/data/job_store/jobs.sqlite3
ENV JUG_GIS_CITIES_ARTIFACT_DIR=/data/job_store/artifacts

# Default data mount locations inside the container.
ENV JUG_GIS_CITIES_SAINT_MALACHIE_DATA_DIR=/data/saint_malachie_gisoo_data
ENV JUG_GIS_CITIES_MTL_FSA_DATA_DIR=/data/mtl_gisoo_fsa_data

RUN mkdir -p \
    /app/logs \
    /data/job_store \
    /data/saint_malachie_gisoo_data \
    /data/mtl_gisoo_fsa_data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "app:app"]
