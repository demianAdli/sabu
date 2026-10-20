# JUG GIS Cities Contract Artifacts

This folder contains example payloads and runtime configuration artifacts for
`jug_gis_cities`.

The currently implemented HTTP API triggers an installed component by name:

```text
POST /components/{component_name}/runs
POST /components/{component_name}/batch-runs
GET /components/{component_name}/batch-runs/{batch_id}
GET /artifacts/{artifact_id}/download
```

The request body accepts `mode` and, for FSA-capable components, `fsa`:

- `standardize`: run the component workflow and then the contract adapter.
- `independent`: run only the component workflow.
- `fsa`: optional three-character FSA, required by `mtl_fsa_gisoo`.

Batch submission accepts exactly one of selected `fsas` or `all_fsas=true`,
plus `max_workers`. It returns `202 Accepted`; the status endpoint reports
persistent progress and ordered per-FSA results.

Successful standardized runs and successful standardized per-FSA results expose
`standardized_artifact_id` and an absolute `standardized_download_url` in addition
to the unchanged output paths. Independent runs, failures, and legacy batch
results without registrations return null artifact fields. Follow the URL to
download the existing `application/geo+json` attachment without preprocessing or
shared filesystem access. The GeoJSON content contract is unchanged.

Each registration retains a separate copy under a new ID, so reruns and workflow
cleanup cannot replace older downloads. SQLite registrations and copies survive
service restarts when `JUG_GIS_CITIES_ARTIFACT_DIR` is persisted and shared by the
API and worker. Compose uses `/data/job_store/artifacts` in the existing named
job-store volume. Copies are retained indefinitely, with no automatic expiry;
see the service README for storage configuration and operator cleanup guidance.
Only registered IDs are downloadable; caller-selected filesystem paths and
unregistered files are not served. Unknown IDs return 404, missing/unavailable
registered copies return 410, and registry or unexpected read failures return
500 using the existing JSON error envelope.

Dataset manifests in this folder describe flexible input references for direct,
Docker, and future API-oriented execution. The current HTTP endpoint does not
accept those manifests yet.

Files
- `api_run_standardize.request.json`: Example API body for standardized mode.
- `api_run_standardize.response.201.json`: Example standardized-mode API response.
- `api_run_independent.request.json`: Example API body for independent mode.
- `api_run_independent.response.201.json`: Example independent-mode API response.
- `api_run_mtl_fsa_independent.request.json`: Example Montreal FSA API body.
- `api_run_mtl_fsa_independent.response.201.json`: Example Montreal FSA API response.
- `api_batch_all_fsas.request.json`: Example whole-component FSA batch request.
- `api_batch_all_fsas.response.202.json`: Example queued batch response.
- `api_batch_status.response.200.json`: Example completed batch with partial failure.
- `direct_application_config.standardize.json`: Example direct/application configuration.
- `docker_mounted_path_config.json`: Example Docker mounted-path configuration.
- `workflow_input_manifest.saint_malachie.example.json`: Role-based source dataset manifest.
- `standardized_output.example.geojson`: Example strict standardized GeoJSON output.
- `error.response.400.invalid_component_name.json`: Example invalid component-name error.
- `error.response.404.component_not_found.json`: Example component-not-found error.
- `error.response.404.artifact_not_found.json`: Example unknown artifact error.
- `error.response.410.artifact_unavailable.json`: Example unavailable registered copy.
- `error.response.422.invalid_mode.json`: Example validation error for unsupported mode.
- `error.response.422.component_contract.json`: Example component contract error.

Notes
- Input datasets are referenced by path or URI, not embedded.
- Example paths are generic container-style or public-style paths, not local
  workstation paths.
- `saint_malachie_gisoo` is used for the baseline examples, and
  `mtl_fsa_gisoo` is used for FSA run-parameter examples.
