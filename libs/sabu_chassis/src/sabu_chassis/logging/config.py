from __future__ import annotations

import os
import sys
import json
import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Any

try:
    from importlib.resources import files as ir_files  # py>=3.9
except Exception:  # pragma: no cover
    ir_files = None  # type: ignore[assignment]


DEFAULT_CONFIG_RESOURCE = 'logging_config.json'


def infer_service_name() -> str:
    """
    Infer LOG_SERVICE using your naming convention and a few env knobs.

    Precedence:
      1) LOG_SERVICE (explicit)
      2) infer core name from a parent directory (default pattern: 'jug_<core>')
      3) fallback core name (default: 'jugs')

    Composition:
      f'{LOG_SERVICE_PREFIX}{core}{LOG_SERVICE_SUFFIX}'

    Env knobs:
      - LOG_SERVICE_PREFIX: default ''
      - LOG_SERVICE_SUFFIX: default '-api'
      - LOG_SERVICE_FALLBACK: default 'jugs'
      - LOG_SERVICE_DIR_PREFIX: default 'jug_'   (what to look for in directory names)
      - LOG_SERVICE_STRIP_PREFIX: default 'jug_' (what to strip before composing)
        (You can set both DIR_PREFIX and STRIP_PREFIX to keep them consistent.)
    """
    explicit = os.getenv('LOG_SERVICE')
    if explicit:
        return explicit

    prefix = os.getenv('LOG_SERVICE_PREFIX', '')
    suffix = os.getenv('LOG_SERVICE_SUFFIX', '-api')
    fallback_core = os.getenv('LOG_SERVICE_FALLBACK', 'jugs')

    dir_prefix = os.getenv('LOG_SERVICE_DIR_PREFIX', 'jug_')
    strip_prefix = os.getenv('LOG_SERVICE_STRIP_PREFIX', dir_prefix)

    def _scan_up(start: Path) -> str | None:
        for parent in [start, *start.parents]:
            name = parent.name
            if dir_prefix and name.startswith(dir_prefix) and len(name) > len(dir_prefix):
                core = name
                if strip_prefix and core.startswith(strip_prefix):
                    core = core[len(strip_prefix):]
                core = core.strip('-_ ')
                if core:
                    return f'{prefix}{core}{suffix}'
        return None

    # Prefer sys.argv[0] location (often closer to service root than cwd)
    try:
        argv0 = Path(sys.argv[0]).resolve()
        hit = _scan_up(argv0.parent)
        if hit:
            return hit
    except Exception:
        pass

    # Fallback to cwd scan
    try:
        hit = _scan_up(Path.cwd().resolve())
        if hit:
            return hit
    except Exception:
        pass

    return f'{prefix}{fallback_core}{suffix}'


def _load_default_config_from_package() -> dict[str, Any]:
    if ir_files is None:
        raise RuntimeError('importlib.resources.files is unavailable; need Python 3.9+')

    pkg_root = __package__.split('.')[0]  # 'jugs_chassis'
    cfg_path = ir_files(pkg_root).joinpath('logging').joinpath(DEFAULT_CONFIG_RESOURCE)
    raw = cfg_path.read_text(encoding='utf-8')
    return json.loads(raw)


def load_config(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return _load_default_config_from_package()

    p = Path(path)
    raw = p.read_text(encoding='utf-8')
    return json.loads(raw)


def apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    root = cfg.setdefault('root', {})
    root['level'] = os.getenv('LOG_LEVEL', root.get('level', 'INFO'))

    loggers = cfg.setdefault('loggers', {})
    werk = loggers.setdefault('werkzeug', {})
    werk['level'] = os.getenv('WERKZEUG_LEVEL', werk.get('level', 'INFO'))

    # These are used by ContextFilter; keep LOG_SERVICE as a reliable override.
    os.environ.setdefault('LOG_SERVICE', infer_service_name())
    os.environ.setdefault('LOG_ENV', os.getenv('LOG_ENV', 'dev'))

    return cfg


def _env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def prepare_file_handler(cfg: dict[str, Any]) -> dict[str, Any]:
    handlers = cfg.get('handlers', {})
    fh = handlers.get('file')

    if not isinstance(fh, dict):
        return cfg

    filename = fh.get('filename')
    if not filename:
        return cfg

    env_filename = os.getenv('LOG_FILE_NAME')
    if env_filename:
        filename = env_filename
        fh['filename'] = filename

    base = Path(os.getenv('LOG_DIR_BASE', Path.cwd()))
    file_path = Path(filename)
    if not file_path.is_absolute():
        file_path = base / file_path

    file_path.parent.mkdir(parents=True, exist_ok=True)

    fh['filename'] = str(file_path)
    fh.setdefault('encoding', 'utf-8')
    fh.setdefault('mode', 'a')

    file_level = os.getenv('LOG_FILE_LEVEL')
    if file_level:
        fh['level'] = file_level

    max_bytes = _env_int('LOG_FILE_MAX_BYTES')
    if max_bytes is not None and max_bytes > 0:
        fh['maxBytes'] = max_bytes

    backup_count = _env_int('LOG_FILE_BACKUP_COUNT')
    if backup_count is not None and backup_count >= 0:
        fh['backupCount'] = backup_count

    return cfg


def configure_logging(path: str | Path | None = None) -> None:
    cfg = load_config(path)
    cfg = apply_env_overrides(cfg)
    cfg = prepare_file_handler(cfg)

    try:
        dictConfig(cfg)
    except Exception:
        import traceback, pprint
        print('stderr handler cfg:')
        pprint.pp(cfg.get('handlers', {}).get('stderr'))
        traceback.print_exc()
        raise

    logging.captureWarnings(True)
