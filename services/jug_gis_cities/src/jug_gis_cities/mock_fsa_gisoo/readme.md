# mock_fsa_gisoo

Run the FSA GISOO cleaning and standardization workflow with synthetic data.

## Setup

Use a QGIS-enabled Python environment with `citygisoo` and `jug_gis_cities`
installed. Follow the [standalone PyQGIS setup tutorial in the latest CityGISOO
README on PyPI](https://pypi.org/project/citygisoo/#setting-up-an-environment-to-use-standalone-pyqgis---how-to-import-qgiscore)
for QGIS environment setup and dependency installation. See the
[service README](../../../README.md#install-for-local-runs) for local service installation.

The command below uses the local `pyqgis_sabu` launcher; replace it with your
configured QGIS Python launcher if named differently. Set
`JUG_GIS_CITIES_QGIS_PATH` to the QGIS prefix matching that launcher.

Input files default to `D:/GIS/mock_gisoo_fsa_data/input_data`. Override the
data root with `JUG_GIS_CITIES_MOCK_FSA_DATA_DIR` if needed. In
`workflow_config.py`, the FSA input must point to `synthetic_fsa.gpkg`, which
contains the `g_fsa` field.

## Run

From the Sabu repository root in PowerShell:

```powershell
pyqgis_sabu -m jug_gis_cities `
  --component mock_fsa_gisoo `
  --mode standardize `
  --all-fsas `
  --max-workers 2 `
  --cleanup-outputs
```

To run only the first mock FSA, `T1A`:

```powershell
pyqgis_sabu -m jug_gis_cities `
  --component mock_fsa_gisoo `
  --mode standardize `
  --fsa T1A `
  --cleanup-outputs
```

The second mock FSA is `T2B`; replace `--fsa T1A` with `--fsa T2B` to run it.

Omit `--cleanup-outputs` to keep all intermediate outputs. Outputs default to
`D:/GIS/mock_gisoo_fsa_data/output_data`, grouped by FSA; override this with
`JUG_GIS_CITIES_MOCK_FSA_OUTPUT_DIR`.
