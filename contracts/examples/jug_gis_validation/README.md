# JUG GIS Validation Contract Artifacts

This folder contains example payloads for the `jug_gis_validation` HTTP API.

Files
- `uniquifications.request.json`: Standalone request with duplicates, a tie, and a missing identifier
- `uniquifications.response.200.json`: Retained GeoJSON, counts, and complete record mappings
- `uniquifications.response.422.json`: Invalid duplicate-group area error
- `validations.request.geojson`: Raw GeoJSON body for `POST /validations`
- `validations.request.wrapper.json`: Wrapped JSON body for `POST /validations`
- `validations_path.request.json`: Path-based JSON body for `POST /validations`
- `validations.response.201.json`: Example JSON success response
- `validations.response.200.csv`: Example CSV download response for `POST /validations?export=csv`
- `validations.response.400.invalid_json.json`: Example invalid JSON error response
- `validations.response.422.validation.json`: Example validation/data-contract error response

Notes
- `POST /uniquifications` runs only the existing uniquification policy, without census loading, comparisons, or plots. Supply a wrapper with `unique_attribute_key`, optional `area_key` (default `area`), and exactly one of `buildings_set` (FeatureCollection) or `buildings_set_path`.
- The standalone response contains `retained_geojson`, `uniquification` counts, and one `records` entry per input position. `record_ref` is `record:<zero-based input position>`, so duplicate/missing source IDs remain distinguishable. Each `retained_record_ref` identifies the winner and `retained_feature_index` locates it in the GeoJSON. Retained records map to themselves.
- Standalone request fields and query options are intentionally limited: census/comparison options are rejected. Existing `/validations` behavior remains available.
- `POST /validations` accepts either a raw GeoJSON FeatureCollection or a wrapper object containing `buildings_set` or `buildings_set_path`.
- `POST /validations/upload` accepts a multipart `geojson_file` whose content matches `validations.request.geojson`.
- `POST /validations` and `POST /validations/upload` support `?export=csv`, `?export=plot`, and `?export=geojson`.
- Path-based inputs must use paths visible to the running service. In Docker Compose, host input data can be mounted under `/data/gis`.
- Optional `unique_attribute_key` uniquifies only the validation snapshot. Duplicate ranking uses `uniquification_area_key` when provided, otherwise `area_key`.
- `cleaned_units_num_key` optionally selects a per-feature unit-count property; NULL contributes one, while omitting the setting preserves feature counting.
- `area_calculation_mode` selects `none`, `area-only`, or `area-times-floor`; `include_height_proxy` adds the separately labeled height-proxy diagnostic and cannot be used with `none`.
- `height_proxy_area_key` can differ from `area_key`; `?export=geojson` returns the exact post-uniquification snapshot and requires `unique_attribute_key`.
- Height-proxy area fallback can use `height_proxy_area_fallback_key` or `height_proxy_area_fallback_value`, but not both; omitting both uses the constant `80.0` default.
- The exact `errors` structure in 422 responses can vary with `flask-smorest`/marshmallow versions.
