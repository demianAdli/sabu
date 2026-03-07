# citygisoo

Project Developer: Alireza Adli

## What Is citygisoo

`citygisoo` is a Python package that leverages PyQGIS functions related to geospatial data cleaning for buildings, with the goal of helping develop automated cleaning pipelines.

The name `citygisoo` stands for **Object-Oriented Geographic Information System for Cities**.

The package is developed with an object-oriented approach. The main class is `ScrubLayer`, which centralizes key cleaning and transformation operations used in city-scale workflows.

## Approach and Scope

`citygisoo` uses existing PyQGIS functionalities and, where needed, extends or combines them to support additional operations required for geospatial data-cleaning automation.

This design and methodology will be discussed in more detail in upcoming papers and reports.

## citygisoo in JUGS

`citygisoo` is a shared library and a part of the JUGS project.

JUGS is a sector-based carbon-emission evaluation framework built with a microservices architecture.

Each module runs as an independent service (a "jug"). Current services focus on building life-cycle assessment and city-scale geospatial cleaning/validation workflows. Alongside services, JUGS also includes shared Python libraries such as `jugs-chassis` to provide reusable internal functionality.

## Testing and Publication Context

`citygisoo` was first tested on Montreal island geospatial data.

It is now being published so it can be used for more cities by simply installing the package with `pip`.

## Main Class

### ScrubLayer

`ScrubLayer` is the core class of the package. It wraps and orchestrates essential PyQGIS operations used in geospatial cleaning workflows and provides higher-level methods to automate multi-step tasks.

## Setting up an environment to use standalone PyQGIS - How to import qgis.core

To use PyQGIS without having the QGIS application run in the background, one needs to add the python path to the environment variables. Here is how to do it on Windows:

1. Install QGIS.

2. Assign a specific name to the QGIS Python executable.
   This is done to access QGIS Python from command prompt without mixing with the system Python installation(s).

   a. Go to the QGIS installation directory's Python folder (for example: `C:\Program Files\QGIS 3.34.1\apps\Python39`).
   b. Rename the Python executable (`python.exe`) to a specific desired name, for example `pythonqgis.exe`.

3. Update environment variables.

   a. Open Environment Variables from Windows Start.
   b. Edit `Path` and add:

   > `C:\Program Files\QGIS 3.34.1\apps\Python39`

   c. Create/Edit `PYTHONPATH` and add (separated by semicolons):

   > i. `C:\Program Files\QGIS 3.34.1\apps\qgis\python`
   > ii. `C:\Program Files\QGIS 3.34.1\apps\qgis\python\plugins`
   > iii. `C:\Program Files\QGIS 3.34.1\apps\Qt5\plugins`
   > iv. `C:\Program Files\QGIS 3.34.1\apps\gdal\share\gdal`
   > v. Or all together: `C:\Program Files\QGIS 3.34.1\apps\qgis\python;C:\Program Files\QGIS 3.34.1\apps\qgis\python\plugins;C:\Program Files\QGIS 3.34.1\apps\Qt5\plugins;C:\Program Files\QGIS 3.34.1\apps\gdal\share\gdal`

4. Validate importing `qgis.core`.

   a. Open a command prompt window.
   b. Run `pythonqgis`.
   c. If setup is correct, there should be no import error.
   d. In Python, run:

   > `import qgis.core`

## Name and Dedication

In Farsi, `gisoo` means long hair, especially long or braided hair, often associated with women.

I developed this project after the Woman, Life, Freedom movement in Iran. This movement was initiated after Mahsa Jina Amini was killed by the Islamic Republic police because she did not wear hijab based on their rules.

The map of Montreal island reminded me of a ponytail of a `gisoo`, and I named the project "Gisoo" in honor of the brave women who have struggled for freedom in Iran.

Since the Woman, Life, Freedom movement, the restrictions around the hijab in Iran are no longer enforced in the same way as before, even though there has been no formal legal change.
