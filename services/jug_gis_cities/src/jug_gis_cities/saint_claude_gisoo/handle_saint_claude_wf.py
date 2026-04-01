"""
handle_mtl_ds_workflow module
The workflow of cleaning and updating the Montreal Buildings dataset.
This workflow only processes the Greater Montreal district 111
which includes our CERC office.
The district 111 is a name made in a software project refering
to a municipality (name will be added later)
In Code comments I refer to this district as CERC.
Project Developer: Alireza Adli 
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from citygisoo.scrub_layer_class import ScrubLayer
from jug_gis_cities.saint_claude_gisoo import input_paths_and_layers as paths

# Making folders for the output data layers
paths.create_output_folders(paths.output_paths, paths.output_paths_dir)

cerc_boundary = \
  ScrubLayer(
    paths.qgis_path,
    paths.input_paths['CERC Boundary'],
    'CERC Boundary')
