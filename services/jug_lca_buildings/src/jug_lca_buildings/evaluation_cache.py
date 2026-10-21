"""
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com

Prepare an explicitly identified cache directory for evaluation runs.

This opt-in command records declared provenance, not code or data fingerprints.
It does not participate in normal application calls or change request hashes.
"""

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import platform

from .storage import EmissionsArtifactStore


MANIFEST_NAME = 'evaluation_configuration.json'
REFERENCE_DATA = (
    'nrcan_archetypes.json',
    'nrcan_constructions_cap_3.json',
    'nrcan_materials_dictionaries.json',
    'nrcan_transparent_surfaces_dictionaries.json',
    'cerc-hub-data',
)


def _require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} must be a nonempty string')


def _validate_configuration(configuration):
    if not isinstance(configuration, dict):
        raise ValueError('configuration must be a JSON object')
    for field in ('configuration_label', 'source_revision', 'local_changes'):
        _require_text(configuration.get(field), field)
    references = configuration.get('reference_data')
    if not isinstance(references, dict):
        raise ValueError('reference_data must map data names to revision identifiers')
    for name in REFERENCE_DATA:
        _require_text(references.get(name), f'reference_data.{name}')
    if not isinstance(configuration.get('calculation_settings'), dict):
        raise ValueError('calculation_settings must be an object ({} for defaults)')


def _software_environment():
    # Record the full installed environment, including transitive dependencies.
    # Source/editable modifications still require explicit declared revisions.
    distributions = sorted(
        (distribution.metadata['Name'], distribution.version)
        for distribution in metadata.distributions()
        if distribution.metadata['Name']
    )
    return {
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'platform': platform.platform(),
        'installed_distributions': [
            {'name': name, 'version': version} for name, version in distributions
        ],
    }


def prepare_evaluation_cache(configuration, *, reuse=False):
    """Create provenance once, or check it before deliberately reusing a cache.

    Run in the same software environment and working directory as evaluation.
    Existing artifacts and manifests are never overwritten or deleted.
    """
    _validate_configuration(configuration)
    configured_dir = os.environ.get('JUG_LCA_ARTIFACTS_DIR', '')
    if not configured_dir.strip():
        raise ValueError('Set JUG_LCA_ARTIFACTS_DIR explicitly for evaluation')
    cache_dir = Path(configured_dir).resolve()
    manifest_path = cache_dir / MANIFEST_NAME
    provenance = {
        'schema_version': 1,
        'configuration': configuration,
        'software_environment': _software_environment(),
        'cache_namespace': EmissionsArtifactStore.CACHE_NAMESPACE,
        'cache_directory': str(cache_dir),
    }

    if manifest_path.exists():
        if not reuse:
            raise ValueError('Cache already prepared; use --reuse for the same configuration')
        recorded = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not isinstance(recorded, dict):
            raise ValueError('Invalid evaluation manifest; select a fresh directory')
        recorded.pop('created_at_utc', None)
        if recorded != provenance:
            raise ValueError('Configuration or environment differs; select a fresh directory')
        return manifest_path

    if reuse:
        raise ValueError('Cannot reuse a directory without an evaluation manifest')
    if cache_dir.exists() and any(cache_dir.iterdir()):
        raise ValueError('Cache directory is not empty; select a fresh directory')

    cache_dir.mkdir(parents=True, exist_ok=True)
    provenance['created_at_utc'] = datetime.now(timezone.utc).isoformat()
    # Exclusive creation also prevents accidental replacement by another setup.
    with manifest_path.open('x', encoding='utf-8') as manifest:
        json.dump(provenance, manifest, indent=2, sort_keys=True, ensure_ascii=False)
        manifest.write('\n')
    return manifest_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True, type=Path,
                        help='JSON file declaring source, data revisions, and settings')
    parser.add_argument('--reuse', action='store_true',
                        help='Verify an already prepared cache without changing it')
    args = parser.parse_args(argv)
    try:
        configuration = json.loads(args.configuration.read_text(encoding='utf-8'))
        manifest = prepare_evaluation_cache(configuration, reuse=args.reuse)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(manifest)


if __name__ == '__main__':
    main()
