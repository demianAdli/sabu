"""
Sabu project
jug_sim_buildings package
schemas module
Describe the health response.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from marshmallow import Schema, fields


class HealthResponseSchema(Schema):
    """Process health response."""

    service = fields.String(required=True)
    status = fields.String(required=True)
