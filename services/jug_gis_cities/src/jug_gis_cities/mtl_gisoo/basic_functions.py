"""
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
import processing

from qgis.core import QgsApplication
from qgis.analysis import QgsNativeAlgorithms


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
    print(f"Created folder: {folder_path}")


def merge_las_layers(layers_path, mergeded_layer_path):
  merging_layers = find_las_files(layers_path)
  QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

  params = {'LAYERS': merging_layers,
            'CRS': None,
            'OUTPUT': mergeded_layer_path}

  processing.run("native:mergevectorlayers", params)