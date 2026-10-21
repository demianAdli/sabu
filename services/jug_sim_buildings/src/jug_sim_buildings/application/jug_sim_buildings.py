"""
Sabu project
jug_sim_buildings package
jug_sim_buildings module
Provide framework-independent service health.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

def get_health() -> dict[str, str]:
    """Report process health without running scenarios or external checks."""
    return {'service': 'jug_sim_buildings', 'status': 'ok'}
