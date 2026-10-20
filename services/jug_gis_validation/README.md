# GISOO Validation

**Project Developer:**  
**Alireza Adli**  
alireza.adli4@gmail.com  
alireza.adli@mail.concordia.ca  
[www.demianadli.com](https://demianadli.com/)

---

## Overview

The service also offers standalone uniquification through the `uniquify` CLI
command and `POST /uniquifications`. These run the existing feature selector
without loading census data, comparing datasets, or generating plots.

**GISOO Validation** service is responsible for comparing cleaned geospatial datasets with census data to ensure consistency, completeness, and accuracy at the district level.

This validation module is part of the larger **Sabu framework**, supporting disaggregated carbon-emissions evaluation beginning from the building sector. It integrates naturally with CityGISOO’s automated cleaning workflows and provides a lightweight, extensible interface to perform data verification across postal-code prefixes (FSA).

According to the design description, the validator:

- Supports very large datasets and produces comparisons efficiently.
- Allows categorization by any user-defined factor.
- Outputs results in multiple formats (Python dictionary, DataFrame, CSV, plots).
- Is designed to work with **any city dataset** following cleaning and preparation through CityGISOO.

Repository path:  
https://github.com/demianAdli/sabu/tree/main/services/jug_gis_validation

---

## Table of Contents

- [Main Classes](#main-classes)
- [Features](#features)
- [Recommended Usage](#recommended-usage)
- [Outputs](#outputs)
- [Architecture](#architecture)
- [Contact](#contact)

---

## Main Classes

### ValidateGISOO

Coordinates the entire validation workflow:

- Loads district GeoJSON data
- Loads census CSV files
- Applies prefix-based (FSA) comparisons
- Adjusts values using floor counts when needed
- Filters by building function (optional)
- Produces aggregated comparison tables and reports

The class follows an _immutable-by-convention_ snapshot pattern to maintain reproducibility.

### DistrictGeoJSONAnalysis

Provides auxiliary district-level preprocessing:

- Postal-code prefix extraction
- Summaries by FSA
- Detection of missing or zero values
- Preparation of structures used by `ValidateGISOO`

---

## Features

- Prefix-based validation (first 3 characters of postal code)
- Flexible choice of validation fields (units, area, custom)
- Optional feature-based or attribute-based cleaned-unit counting
- Explicit `none`, `area-only`, or `area-times-floor` calculation modes
- Optional height-derived floor proxy diagnostic
- Optional filtering by building function
- Missing and zero-value detection
- Optional validation-only feature uniquification by an attribute, retaining
  the feature with the greatest configured area
- Extremely fast validation even for large datasets
- Designed to be highly extensible within the CityGISOO ecosystem

Uniquification is disabled by default. For Montreal standardized data, set
`unique_attribute_key` to `roll_provincial_id`. By default, duplicate ranking
uses `area_key`; set `uniquification_area_key` when ranking should use a
different field. For example, validation can calculate with `roll_area` while
duplicate selection uses `citygisoo_area`. This filters only the validator's
in-memory snapshot; it does not rewrite or delete cleaned GeoJSON features.

The default area calculation mode is `area-times-floor`, which preserves the
existing `area_key * floor_num_key` behavior. Use `area-only` when `area_key`
already represents total building area; in that mode `floor_num_key` is not
required. Use `none` to omit area comparison entirely; building area, floor,
and height fields are then not required unless an area field is separately
needed to rank duplicates during uniquification. `none` cannot be combined
with the height proxy. Height-proxy output is disabled by default and can be requested with
`include_height_proxy` or the CLI flag `--include-height-proxy`. Its base area
defaults to `area_key`; use `height_proxy_area_key` or
`--height-proxy-area-key` to select a different field. Unusable proxy-area
values can fall back to either `height_proxy_area_fallback_key` or
`height_proxy_area_fallback_value`. The choices are mutually exclusive; when
neither is supplied, the constant fallback defaults to `80.0`. Results report
the number and percentage of evaluated features that used the fallback.

By default, `Cleaned Units Num` remains the number of retained features. Set
`cleaned_units_num_key` (or CLI option `--cleaned-units-num-key`) to sum a
feature property such as `unit_num` instead. A NULL value contributes one unit;
other values must be finite, non-negative integers. Unit aggregation happens
after optional uniquification and uses the same building-function filter as the
existing validation workflow.

Python and CLI callers can persist the exact post-uniquification validation
snapshot with `uniquified_output_path` or `--uniquified-output-path`. The REST
API returns the same snapshot with `?export=geojson`. GeoJSON export requires
`unique_attribute_key`; the source dataset is never modified.

### Standalone uniquification

Run only uniquification with:

```powershell
python -m jug_gis_validation uniquify --buildings-set input.geojson --unique-attribute-key roll_provincial_id --area-key citygisoo_area --output-path result.json
```

Omit `--output-path` to receive the complete JSON result on stdout. The output
file is a result envelope containing GeoJSON and provenance, not a bare
GeoJSON file. Extract `retained_geojson` when a separate GeoJSON file is needed.
The input is never rewritten; output paths referring to the input, including
hard-link aliases, are rejected. CLI exit codes are `0` for success, `2` for
argument errors, and `1` for processing or output errors, with errors on stderr.

The equivalent synchronous API call is:

```http
POST /uniquifications
Content-Type: application/json

{
  "buildings_set_path": "/data/gis/input.geojson",
  "unique_attribute_key": "roll_provincial_id",
  "area_key": "citygisoo_area"
}
```

Use `buildings_set` with a GeoJSON FeatureCollection instead of
`buildings_set_path` for inline data. Supply exactly one input source.
`unique_attribute_key` is required; `area_key` defaults to `area` and is used
only for ranking. Census, postal-code, function, floor, and height fields are
not required. Other request fields and query options are rejected.

Python callers use
`GISUniquificationApplicationService.run_uniquification(buildings_set,
unique_attribute_key='roll_id', area_key='area')`, exported from
`jug_gis_validation.application`. The returned result exposes
`retained_features`, `uniquification_stats`, and `records`; `as_dict()` produces
the same envelope returned by the API and CLI.

The existing selection policy applies unchanged: keep the greatest numeric
configured area per non-missing identifier, breaking maximum-area ties by
earliest input position. Missing/null/blank identifiers remain independent.
Missing, nonnumeric, or non-finite areas fail within duplicate groups only;
they remain permitted on singleton or missing-identifier records. Zero and
negative numeric areas are not rejected. Required columns must still exist.
Retained features preserve input order. Standalone file inputs use the same
JSON-to-frame conversion as inline inputs to avoid file-driver coercion;
existing validation file loading remains unchanged.

Success returns HTTP `200` with:

- `uniquification`: existing statistics, including input/retained/removed counts
  and the number of duplicate groups.
- `retained_geojson`: retained geometries and properties in a FeatureCollection.
- `records`: one entry per input position, containing `record_ref`,
  `input_position`, configured `identifier` and `area` values, `status`,
  `retained_record_ref`, `retained_feature_index`, and `reason`.

`record_ref` is `record:<zero-based input position>`. It does not depend on
original GeoJSON IDs, identifier properties, or DataFrame index labels, so
missing or duplicated IDs and identical records remain distinguishable.
References apply to this ordered input, not to reordered datasets. Original
top-level GeoJSON IDs are not synthesized in the retained output; tracing uses
input positions. Removed records point to the winning `retained_record_ref`;
retained records point to themselves. `retained_feature_index` locates the
winner in `retained_geojson.features`. Consequently, input count equals trace
length, retained count equals GeoJSON length, and retained plus removed equals
input count. Missing/non-finite scalar values serialize as JSON `null`.

Reasons are `missing_identifier`, `unique_identifier`, `largest_area`,
`earliest_maximum_area`, `smaller_area`, and `later_tied_maximum`. The first
four explain retained records; the last two explain removals.

API errors use the existing `message`/optional `errors` envelope: `400` for
invalid JSON, unreadable inputs, malformed GeoJSON, or unsupported query
options; `422` for invalid request fields, missing configured columns,
unusable identifiers, or invalid duplicate-group areas; `500` for unexpected
failures with a generic public message. No jobs or server-side outputs are
created by this endpoint.

See the [standalone request example](../../contracts/examples/jug_gis_validation/uniquifications.request.json)
and [response example](../../contracts/examples/jug_gis_validation/uniquifications.response.200.json).

---

# Recommended Usage

## Use the Interactive Workflow (Jupyter Notebook)

The recommended way to use this module is through the interactive notebook:

**`interactive_validation_wf.ipynb`**

GitHub provides reliable `.ipynb` rendering, so **please use the following link**:

👉 **https://github.com/demianAdli/sabu/blob/main/services/jug_gis_validation/notebooks/interactive_validation_wf.ipynb**

Gitea currently has issues rendering Jupyter notebooks, so GitHub is the preferred viewer.

---

## Outputs

The validation workflow can generate:

- **Python dictionaries**
- **Pandas DataFrames**
- **CSV summary files**
- **Plots** for visual comparison

These outputs allow different levels of integration—from automated pipelines to manual inspection.

---

## Architecture

The validation service fits into the broader **Sabu framework**, following a modular and extensible microservice-based design:

- Uses a generic, city-agnostic workflow structure
- Can be orchestrated with GISOO-based services to validate their results
- Can be executed as a standalone service or embedded in a more automated sequence
- Supports the architectural goals of Sabu: modularity, reusability, and scalability

---

## Contact

**Alireza Adli**  
alireza.adli4@gmail.com  
alireza.adli@mail.concordia.ca
www.demianadli.com
