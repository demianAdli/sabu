# GISOO Validation

**Project Developer:**  
**Alireza Adli**  
alireza.adli4@gmail.com  
alireza.adli@mail.concordia.ca  
[www.demianadli.com](https://demianadli.com/)

---

## Overview

**GISOO Validation** service is responsible for comparing cleaned geospatial datasets with census data to ensure consistency, completeness, and accuracy at the district level.  
The **conceptual basis for incorporating census data into the validation workflow comes from work and discussions with Oriol Gavalda (oriol.gavalda@concordia.ca)**, particularly regarding how census units can be related to district-level building datasets.

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
- Floor-adjusted metrics where applicable
- Optional filtering by building function
- Missing and zero-value detection
- Extremely fast validation even for large datasets
- Designed to be highly extensible within the CityGISOO ecosystem

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
