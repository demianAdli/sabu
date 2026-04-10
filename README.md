# Sabu

**Sabu** is a software framework designed to evaluate carbon emissions in a **sector-based** manner.  
The framework follows a **microservices architecture**, in which each independent module operates as an autonomous service—referred to as a _jug_.

---

## Table of Contents

- [Sabu](#sabu)
  - [Services](#services)
  - [Shared Libraries](#shared-libraries)
  - [Development and Collaboration](#development-and-collaboration)

---

## Services

- **`jug_lca_buildings`**  
  Evaluates carbon emissions for the **Embodied** and **End-of-Life** stages of a building’s Life Cycle Assessment (LCA).

- **`jug_gis_cities`**  
  A geospatial data–cleaning service built on the _Object-Oriented Geographic Information System for Cities_ (**CityGISOO**).  
  It provides automated, city-scale geospatial cleaning pipelines.

- **`jug_gis_validation`**  
  Provides validation for geospatial datasets by accepting the output of any automated or non-automated cleaning process as a GeoJSON file.

---

## Shared Libraries

Shared libraries provide reusable, non-deployable components that can be **installed and directly imported as Python packages** to support service development.  
Unlike services, they do not communicate via APIs and are not deployed independently.

- **`jugs_chassis`**  
  A foundational library offering shared infrastructure modules used across services (jugs), such as common utilities, conventions, and cross-cutting concerns.

- **`citygisoo`**  
  A shared library that simplifies the development of geospatial data-cleaning pipelines.  
  It provides object-oriented abstractions over GIS operations and serves as the underlying engine for `jug_gis_cities`.

---

## Development and Collaboration

The project’s **business-value components** have been developed in collaboration with **domain experts**, who are cited in the corresponding repositories.  
The **design and development** of the overall project have been led by **Alireza Adli**.

A mirrored version of this project is hosted on the **Next-Generation Cities Institute (NGCI)** version-control platform, **Gitea**, at Concordia University.
