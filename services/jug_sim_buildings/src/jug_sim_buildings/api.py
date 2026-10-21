"""
Sabu project
jug_sim_buildings package
api module
Create and configure the Flask API.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from collections.abc import Mapping
from secrets import token_hex
from time import perf_counter

from flask import Flask, g, request
from flask_smorest import Api
from sabu_chassis.logging import get_logger
from sabu_chassis.logging.context import get_request_id, set_request_id
from werkzeug.exceptions import HTTPException

from .config import Config
from .logging_setup import configure_service_logging
from .resources.health import blp as health_blueprint


logger = get_logger(__name__)


def create_app(config: Mapping | None = None) -> Flask:
    """Build the HTTP adapter and configure entrypoint logging."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if config is not None:
        app.config.update(config)

    configure_service_logging()
    api = Api(app)
    api.register_blueprint(health_blueprint)

    @app.before_request
    def before_request():
        g._previous_request_id = get_request_id()
        set_request_id(
            request.headers.get('X-Request-ID')
            or request.headers.get('X-Correlation-ID')
            or token_hex(8))
        g._request_started_at = perf_counter()

    @app.after_request
    def after_request(response):
        logger.info(
            'http_request',
            extra={
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
                'latency_ms': int(
                    (perf_counter() - g._request_started_at) * 1000),
                'client_ip': request.headers.get(
                    'X-Forwarded-For', request.remote_addr),
            })
        response.headers['X-Request-ID'] = get_request_id()
        return response

    @app.teardown_request
    def teardown_request(error):
        previous_id = g.pop('_previous_request_id', None)
        if previous_id is not None:
            set_request_id(previous_id)

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        if isinstance(error, HTTPException):
            return error
        logger.exception('unhandled_exception')
        return {'message': 'Internal Server Error'}, 500

    return app
