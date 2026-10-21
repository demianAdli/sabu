"""
Sabu project
jug_sim_buildings package
logging_setup module
Configure service logging through sabu-chassis.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import os
from pathlib import Path

from sabu_chassis.logging import configure_logging


DEFAULT_LOG_FILE_NAME = 'logs/jug_sim_buildings.log'


def configure_service_logging():
    """Apply service defaults while preserving explicit LOG_* settings."""
    os.environ.setdefault('LOG_SERVICE', 'sim_buildings-api')
    os.environ.setdefault('LOG_DIR_BASE', str(Path.cwd()))
    os.environ.setdefault('LOG_FILE_NAME', DEFAULT_LOG_FILE_NAME)
    configure_logging()
