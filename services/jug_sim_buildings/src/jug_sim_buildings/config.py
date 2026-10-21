"""
Sabu project
jug_sim_buildings package
config module
Define API and development-server defaults.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5000


class Config:
    """Flask-Smorest API defaults, overridable through create_app()."""

    API_TITLE = 'Buildings Simulation API'
    API_VERSION = 'v1'
    OPENAPI_VERSION = '3.0.2'
    OPENAPI_URL_PREFIX = '/'
    OPENAPI_SWAGGER_UI_PATH = '/swagger-ui'
    OPENAPI_SWAGGER_UI_URL = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'
