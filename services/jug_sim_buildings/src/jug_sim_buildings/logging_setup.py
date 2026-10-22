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


def _default_log_base():
    service_root = Path(__file__).resolve().parents[2]
    if service_root.name == 'jug_sim_buildings' and (service_root / 'pyproject.toml').is_file():
        return service_root
    # Wheels have no checkout service root; deployments can set LOG_DIR_BASE.
    state_root = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'state'))
    return state_root / 'Sabu' / 'jug_sim_buildings'


def configure_service_logging():
    """Apply service defaults while preserving explicit LOG_* settings."""
    os.environ.setdefault('LOG_SERVICE', 'sim_buildings-api')
    os.environ.setdefault('LOG_DIR_BASE', str(_default_log_base()))
    os.environ.setdefault('LOG_FILE_NAME', DEFAULT_LOG_FILE_NAME)
    configure_logging()
