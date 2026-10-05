"""
CityGISOO
Object-Oriented Geographic Information System for Cities
basic_functions module
A number of functionalities that help the project
but cannot be a part of the PyQGIS tool.
Project Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import os
import glob
import re
import shutil
from pathlib import Path

import processing

from sabu_chassis.logging import get_logger
from qgis.core import QgsApplication
from qgis.analysis import QgsNativeAlgorithms


logger = get_logger(__name__)


def gather_district_geojson_files(
        input_path: str | os.PathLike,
        district_name: str,
        output_path: str | os.PathLike) -> None:
  """Gather standardized subdistrict GeoJSON files into one directory.

  Each immediate child directory of ``input_path`` is treated as a
  subdistrict. For a child named ``<name>``, the expected source file is::

    <district_name>_<name>_gisoo_standardized/
      <district_name>_<name>_gisoo_standardized.geojson

  The source layout is validated in full before any files are copied.

  Args:
    input_path: Directory containing the subdistrict result directories.
    district_name: District prefix used in the result folder and file names.
    output_path: Directory into which the GeoJSON files will be copied.

  Raises:
    TypeError: If ``district_name`` is not a string.
    ValueError: If ``district_name`` is empty or contains a path separator, or
      if the input and output directories are the same.
    FileNotFoundError: If the input directory or any expected GeoJSON file is
      missing.
    NotADirectoryError: If an input or existing output path is not a directory.
  """
  _gather_district_result_files(
    input_path,
    district_name,
    output_path,
    result_name_suffix='_gisoo_standardized',
    file_extension='.geojson',
    format_name='GeoJSON',
    subdistrict_name_pattern=None)


def gather_district_geopackage_files(
        input_path: str | os.PathLike,
        district_name: str,
        output_path: str | os.PathLike) -> None:
  """Gather subdistrict GeoPackage files into one directory.

  Each immediate child directory of ``input_path`` is treated as an FSA. Its
  directory name is inserted into the GeoPackage folder and filename. For
  example, an immediate child directory named ``H1A`` is expected to contain::

    H1A/
      <district_name>_H1A_gisoo/
        <district_name>_H1A_gisoo.gpkg

  Immediate child directories whose names are not three-character FSA codes
  are ignored.

  The source layout is validated in full before any files are copied.

  Args:
    input_path: Directory containing the subdistrict result directories.
    district_name: District prefix used in the result folder and file names.
    output_path: Directory into which the GeoPackage files will be copied.

  Raises:
    TypeError: If ``district_name`` is not a string.
    ValueError: If ``district_name`` is empty or contains a path separator, or
      if the input and output directories are the same.
    FileNotFoundError: If the input directory or any expected GeoPackage file
      is missing.
    NotADirectoryError: If an input or existing output path is not a directory.
  """
  _gather_district_result_files(
    input_path,
    district_name,
    output_path,
    result_name_suffix='_gisoo',
    file_extension='.gpkg',
    format_name='GeoPackage',
    subdistrict_name_pattern=r'[A-Za-z][0-9][A-Za-z]')


def _gather_district_result_files(
        input_path: str | os.PathLike,
        district_name: str,
        output_path: str | os.PathLike,
        result_name_suffix: str,
        file_extension: str,
        format_name: str,
        subdistrict_name_pattern: str | None) -> None:
  if not isinstance(district_name, str):
    raise TypeError('district_name must be a string')
  if not district_name.strip():
    raise ValueError('district_name must not be empty')
  if '/' in district_name or '\\' in district_name:
    raise ValueError('district_name must not contain a path separator')

  input_directory = Path(input_path).expanduser()
  output_directory = Path(output_path).expanduser()

  if not input_directory.exists():
    raise FileNotFoundError(
      f'Input directory does not exist: {input_directory}')
  if not input_directory.is_dir():
    raise NotADirectoryError(
      f'Input path is not a directory: {input_directory}')
  if output_directory.exists() and not output_directory.is_dir():
    raise NotADirectoryError(
      f'Output path is not a directory: {output_directory}')

  resolved_input = input_directory.resolve()
  resolved_output = output_directory.resolve()
  if resolved_input == resolved_output:
    raise ValueError('input_path and output_path must be different directories')

  subdistrict_directories = sorted(
    (
      directory for directory in input_directory.iterdir()
      if (
        directory.is_dir()
        and directory.resolve() != resolved_output
        and (
          subdistrict_name_pattern is None
          or re.fullmatch(subdistrict_name_pattern, directory.name)
        )
      )
    ),
    key=lambda directory: directory.name)

  if not subdistrict_directories:
    raise FileNotFoundError(
      f'No subdistrict directories found in: {input_directory}')

  source_files = []
  missing_files = []
  for subdistrict_directory in subdistrict_directories:
    subdistrict_name = subdistrict_directory.name
    result_name = (
      f'{district_name}_{subdistrict_name}{result_name_suffix}')
    source_file = (
      subdistrict_directory
      / result_name
      / f'{result_name}{file_extension}')
    if source_file.is_file():
      source_files.append(source_file)
    else:
      missing_files.append(source_file)

  if missing_files:
    missing_list = '\n'.join(f'- {path}' for path in missing_files)
    raise FileNotFoundError(
      f'Expected {format_name} files are missing:\n'
      f'{missing_list}')

  output_directory.mkdir(parents=True, exist_ok=True)
  for source_file in source_files:
    shutil.copy2(source_file, output_directory / source_file.name)

  logger.info(
    'Copied %d %s files for district %s to %s',
    len(source_files),
    format_name,
    district_name,
    output_directory)


def find_shp_files(root_folder):
  shp_files = []
  # Sort folders alphabetically
  for foldername, _, _ in sorted(os.walk(root_folder)):
    for filename in sorted(glob.glob(os.path.join(foldername, '*.shp'))):
      new_file_name = filename.replace('\\', r'/')
      shp_files.append(new_file_name)
  return shp_files


def find_las_files(root_folder):
  las_files = []
  # Sort folders alphabetically
  for foldername, _, _ in sorted(os.walk(root_folder)):
    for filename in sorted(glob.glob(os.path.join(foldername, '*.las'))):
      new_file_name = filename.replace('\\', r'/')
      las_files.append(new_file_name)
  return las_files


def create_folders(directory, num_folders):
  """
  Create a specified number of folders in the given directory.

  Args:
  - directory (str): The directory where folders will be created.
  - num_folders (int): The number of folders to create.
  """
  # Check if the directory exists, if not, create it
  if not os.path.exists(directory):
    os.makedirs(directory)

  # Create folders
  for i in range(num_folders):
    folder_name = f"layer_{i}"
    folder_path = os.path.join(directory, folder_name)
    os.makedirs(folder_path)
    logger.info('Created folder: %s', folder_path)


def create_output_folders(paths_dict, output_dir):
  for path in paths_dict.keys():
    new_folder = path.lower().replace(' ', '_')
    output_path = os.path.join(output_dir, new_folder)
    os.makedirs(output_path, exist_ok=True)

    if path[-1] != 's':
      paths_dict[path] = os.path.join(output_path, f'{new_folder}.shp')
    else:
      paths_dict[path] = output_path


def merge_las_layers(layers_path, mergeded_layer_path):
  merging_layers = find_las_files(layers_path)
  QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

  params = {'LAYERS': merging_layers,
            'CRS': None,
            'OUTPUT': mergeded_layer_path}

  processing.run("native:mergevectorlayers", params)
  logger.info('Merged LAS layers into %s', mergeded_layer_path)
