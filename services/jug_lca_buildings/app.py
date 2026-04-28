"""
Sabu project
jug_lca_buildings package
app module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
import logging
import secrets
from time import perf_counter

from flask import Flask, request, g
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

try:
    from jug_lca_buildings.resources.emissions \
        import blp as emissions_blueprint
except ModuleNotFoundError:
    from src.jug_lca_buildings.resources.emissions \
        import blp as emissions_blueprint

from sabu_chassis.logging.config import configure_logging
from sabu_chassis.logging.context import set_request_id, get_request_id

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['API_TITLE'] = 'LCA Carbon Workflow API'
app.config['API_VERSION'] = 'v1'
app.config['OPENAPI_VERSION'] = '3.0.2'
app.config['OPENAPI_URL_PREFIX'] = '/'
app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger-ui'
app.config['OPENAPI_SWAGGER_UI_URL'] = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'

api = Api(app)

api.register_blueprint(emissions_blueprint)


# ---- Correlation ID + access logging ----
@app.before_request
def _before():
    rid = (request.headers.get("X-Request-ID")
           or request.headers.get("X-Correlation-ID")
           or secrets.token_hex(8))
    set_request_id(rid)
    g._t0 = perf_counter()


@app.after_request
def _after(resp):
    try:
        dur_ms = int((perf_counter() - getattr(g, "_t0", perf_counter())) * 1000)
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        logger.info(
            "http_request",
            extra={
                "method": request.method,
                "path": request.path,
                "status": resp.status_code,
                "latency_ms": dur_ms,
                "client_ip": client_ip,
            },
        )
        resp.headers["X-Request-ID"] = get_request_id()
    finally:
        return resp


@app.errorhandler(Exception)
def _unhandled(e):
    if isinstance(e, HTTPException):
        return e
    logger.exception("unhandled_exception")
    return {"message": "Internal Server Error"}, 500
