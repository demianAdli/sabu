"""
Sabu project
jug_sim_buildings package
__main__ module
Run scenario_001 from a JSON configuration file.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import argparse
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run scenario_001 using two upstream HTTP APIs.')
    parser.add_argument('--config', required=True, help='Path to a scenario JSON configuration file.')
    args = parser.parse_args(argv)
    # --help performs no service imports, filesystem writes, or logging setup.
    from .config import ScenarioConfig
    try:
        config = ScenarioConfig.from_file(args.config)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))

    from ..logging_setup import configure_service_logging
    from .workflow import run_scenario
    try:
        configure_service_logging()
        result = run_scenario(config)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
