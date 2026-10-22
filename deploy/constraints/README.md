# GIS dependency baseline

`gis-baseline.txt` records overlapping dependency versions observed in the
working `pyqgis344` environment on 2026-10-22. That launcher currently selects
Python 3.12.13 and QGIS 3.44.9. Its installed dependencies pass
`pip check`. This baseline targets the GIS services and simulation HTTP client.
Set `JUG_GIS_CITIES_QGIS_PATH` to the prefix matching the active launcher;
the component's legacy QGIS path default may refer to a different installation.

Constraints restrict a deliberate installation; they do not install packages or
provide a complete environment lock. Preserve the OSGeo4W-provided QGIS/native
stack. Audit an environment read-only first, then verify intended installations
in a separate environment before changing the working GIS installation. Do not
upgrade packages simply to match another development environment.

Runtime manifests describe each service's own dependencies; constraints select
the tested shared versions. The simulation client does not require QGIS.

Verification used a separate virtual environment with read-only access to the
OSGeo4W site-packages and an offline, constrained installation dry run for the
GIS services, simulation client, chassis, and CityGISOO. No dependency changes
were made to the working GIS installation. This checks the observed stack; it
does not claim a portable, independently reconstructed native environment.

LCA integration remains a separate compatibility boundary: `jug_lca_buildings`
currently requires `sabu-chassis==0.1.0`, which conflicts with this baseline's
0.1.1, and its `cerc-hub` dependency is absent from this GIS environment. Do not
install LCA into this baseline or relax its requirements without testing its own
environment. No LCA dependency compatibility is claimed by the GIS checks.
