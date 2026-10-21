"""
Sabu project
jug_sim_buildings package
app module
Expose the service WSGI application.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from jug_sim_buildings.api import create_app


app = create_app()
