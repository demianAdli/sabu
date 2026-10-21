"""
Sabu project
jug_sim_buildings package
__main__ module
Run the development API server.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import argparse

from .config import DEFAULT_HOST, DEFAULT_PORT


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Run the jug_sim_buildings foundation API.')
    parser.add_argument('--host', default=DEFAULT_HOST)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    from .api import create_app

    create_app().run(host=args.host, port=args.port)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
