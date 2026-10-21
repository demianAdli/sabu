"""
Sabu project
jug_sim_buildings package
health module
Expose service health through HTTP.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from ..application import get_health
from ..schemas import HealthResponseSchema


blp = Blueprint('Health', __name__, description='Service process health.')


@blp.route('/health')
class Health(MethodView):
    @blp.response(200, HealthResponseSchema)
    def get(self):
        """Report service process health."""
        return get_health()
