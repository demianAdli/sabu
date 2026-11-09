"""Safe cleanup of generated Montreal FSA workflow outputs."""
from __future__ import annotations

import os
import gc
import shutil
import time
from pathlib import Path

from sabu_chassis.logging import get_logger

try:
  from . import workflow_config as paths
except ImportError:
  import workflow_config as paths


logger = get_logger(__name__)

_DELETE_RETRY_DELAYS = (0.1, 0.25, 0.5, 1.0)


def _normalize_keep_outputs(keep_outputs):
  if keep_outputs is None:
    return ()
  if isinstance(keep_outputs, (str, bytes)):
    raise TypeError('keep_outputs must be a list, tuple, set, or None.')

  try:
    raw_output_keys = list(keep_outputs)
  except TypeError as exc:
    raise TypeError(
      'keep_outputs must be a list, tuple, set, or None.') from exc

  if any(not isinstance(output_key, str) for output_key in raw_output_keys):
    raise TypeError('keep_outputs must contain only strings.')

  normalized_output_keys = []
  seen = set()
  for output_key in raw_output_keys:
    normalized_output_key = output_key.strip()
    if not normalized_output_key:
      raise ValueError('keep_outputs cannot contain empty output keys.')
    if normalized_output_key not in paths.output_paths:
      valid_output_keys = ', '.join(sorted(paths.output_paths))
      raise ValueError(
        f'Unknown Montreal FSA output key: {normalized_output_key}. '
        f'Valid output keys: {valid_output_keys}.')
    if normalized_output_key not in seen:
      normalized_output_keys.append(normalized_output_key)
      seen.add(normalized_output_key)
  return tuple(normalized_output_keys)


def _resolved_output_key(output_key, fsa):
  return output_key.format(fsa=fsa)


def _cleanup_candidates(keep_outputs):
  retained_keys = set(paths.default_retained_output_keys)
  retained_keys.update(keep_outputs)
  return tuple(
    output_key
    for output_key in paths.output_paths
    if output_key not in retained_keys
  )


def _is_within_directory(candidate, directory):
  try:
    common_path = os.path.commonpath((candidate, directory))
    return os.path.normcase(common_path) == os.path.normcase(
      os.fspath(directory))
  except ValueError:
    # Different Windows drives cannot share a common path.
    return False


def _release_qgis_output_layers(output_root):
  """Release project-owned layers backed by one FSA output directory."""
  try:
    from qgis.core import QgsProject
  except ImportError:
    # Unit tests and config-only consumers do not require a QGIS runtime.
    return 0

  project = QgsProject.instance()
  layer_ids_to_remove = []
  for layer_id, layer in project.mapLayers().items():
    source = layer.source() if callable(getattr(layer, 'source', None)) else ''
    source_path = source.split('|', 1)[0].strip()
    if not source_path:
      continue
    resolved_source_path = Path(source_path).resolve()
    if _is_within_directory(resolved_source_path, output_root):
      layer_ids_to_remove.append(layer_id)
  layer = None

  if layer_ids_to_remove:
    project.removeMapLayers(layer_ids_to_remove)
    logger.info(
      'Released Montreal FSA QGIS output layers. Count=%s Root=%s',
      len(layer_ids_to_remove),
      output_root)

  # ScrubLayer wrappers may participate in reference cycles. Collect after
  # removing project ownership so OGR providers close their file handles.
  gc.collect()
  return len(layer_ids_to_remove)


def _remove_output_directory(output_directory):
  for attempt in range(len(_DELETE_RETRY_DELAYS) + 1):
    try:
      shutil.rmtree(output_directory)
      return
    except PermissionError:
      if attempt >= len(_DELETE_RETRY_DELAYS):
        raise
      delay = _DELETE_RETRY_DELAYS[attempt]
      logger.warning(
        'Montreal FSA output is still locked; retrying deletion. '
        'Path=%s Attempt=%s Delay=%.2fs',
        output_directory,
        attempt + 1,
        delay)
      gc.collect()
      time.sleep(delay)


def cleanup_outputs(
        fsa,
        keep_outputs=None,
        validate_only=False,
        release_qgis_layers=True):
  """Delete unretained known outputs for one successfully completed FSA.

  ``validate_only`` validates caller input without touching the filesystem.
  The application service uses it before starting a potentially long workflow.
  """
  normalized_fsa = paths.normalize_fsa(fsa)
  normalized_keep_outputs = _normalize_keep_outputs(keep_outputs)
  cleanup_candidates = _cleanup_candidates(normalized_keep_outputs)
  if validate_only:
    return ()

  output_root = Path(
    paths.get_fsa_output_paths_dir(normalized_fsa)).resolve()
  deleted_output_paths = []

  if release_qgis_layers:
    _release_qgis_output_layers(output_root)

  for output_key in cleanup_candidates:
    resolved_key = _resolved_output_key(output_key, normalized_fsa)
    output_directory = (output_root / resolved_key).resolve()

    # Known keys should always resolve to direct children. Keep this check at
    # deletion time as defense in depth against future configuration changes.
    if output_directory.parent != output_root:
      raise ValueError(
        'Refusing to clean an output outside the Montreal FSA output '
        f'directory: {output_directory}')
    if not output_directory.exists():
      continue
    if not output_directory.is_dir():
      raise ValueError(
        f'Expected Montreal FSA output directory: {output_directory}')

    _remove_output_directory(output_directory)
    deleted_output_paths.append(os.fspath(output_directory))

  logger.info(
    'Cleaned Montreal FSA workflow outputs. FSA=%s Deleted=%s Retained=%s',
    normalized_fsa,
    len(deleted_output_paths),
    sorted(set(paths.default_retained_output_keys).union(
      normalized_keep_outputs)))
  return tuple(deleted_output_paths)
