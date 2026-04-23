<p align="center">
  <img src="citygisoo_white_3.png" alt="citygisoo logo" width="960">
</p>

# citygisoo

Project Developer: Alireza Adli

## Table of Contents

- [What Is citygisoo](#what-is-citygisoo)
- [Approach and Scope](#approach-and-scope)
- [citygisoo in Sabu](#citygisoo-in-sabu)
- [Testing and Publication Context](#testing-and-publication-context)
- [Main Class](#main-class)
  - [ScrubLayer](#scrublayer)
- [Setting up an environment to use standalone PyQGIS - How to import qgis.core](#setting-up-an-environment-to-use-standalone-pyqgis---how-to-import-qgiscore)
- [Name and Dedication](#name-and-dedication)

## What Is citygisoo

`citygisoo` is a Python package that leverages PyQGIS functions for cleaning building-related geospatial data, with the goal of supporting automated data-cleaning pipelines.

The name `citygisoo` stands for **Object-Oriented Geographic Information System for Cities**.

The package follows an object-oriented design. Its central component is the `ScrubLayer` class, which consolidates key cleaning and transformation operations commonly used in city-scale workflows.

## Approach and Scope

`citygisoo` builds on existing PyQGIS functionality and, where necessary, extends or combines these capabilities to support additional operations required for automated geospatial data cleaning.

The design principles and methodology behind this approach will be discussed in more detail in upcoming papers and reports.

## citygisoo in Sabu

`citygisoo` is a shared library within the Sabu project.

Sabu is a sector-based carbon-emission evaluation framework built on a microservices architecture.

Each module runs as an independent service (a “jug”). Current services focus on building life-cycle assessment and city-scale geospatial cleaning and validation workflows. In addition to these services, Sabu includes shared Python libraries such as `sabu-chassis`, which provide reusable internal functionality.

## Testing and Publication Context

`citygisoo` was initially tested using geospatial data from Montréal Island.

It is now being published so that it can be applied to other cities simply by installing the package via `pip`.

## Main Class

### ScrubLayer

`ScrubLayer` is the core class of the package. It wraps and orchestrates essential PyQGIS operations used in geospatial cleaning workflows and provides higher-level methods for automating multi-step tasks.

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

In Persian, `gisoo` refers to long hair, especially long or braided hair, and the word is most commonly used when speaking about a woman’s hair.

I began developing this project in the aftermath of the Woman, Life, Freedom movement in Iran. The movement emerged following the killing of Mahsa Jina Amini, who died in the custody of the Islamic Republic’s morality police after being arrested for allegedly violating the state’s compulsory hijab rules.

Since the Woman, Life, Freedom movement, the enforcement of hijab restrictions in Iran has changed significantly. Although no formal legal reform has been enacted, the rules are no longer enforced in the same way as before.

While working with geospatial data of Montréal, the shape of the island on the map reminded me of a ponytail—like a gisoo. This association inspired the name of the project. I chose `gisoo` as a small tribute to the courage of the women in Iran who have fought for freedom and human rights.
