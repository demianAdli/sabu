"""
Sabu project
jug_sim_buildings package
config module
Load and validate scenario_001 settings.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


def http_url(value: str) -> str:
    """Require an explicit HTTP origin, without credentials or query options."""
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError('URL must be an HTTP(S) URL without whitespace.')
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or '\\' in value):
        raise ValueError('URL must use HTTP(S), without credentials, query, or fragment.')
    parsed.port  # Reject malformed port specifications now, before any calls.
    return value.rstrip('/')


@dataclass(frozen=True)
class ScenarioConfig:
    """Scenario choices; relative output roots resolve against the config file."""

    gis_cities_url: str
    gis_validation_url: str
    output_root: Path
    fsa: str = 'H2M'
    connect_timeout_seconds: float = 10
    preprocess_read_timeout_seconds: float = 7200
    download_read_timeout_seconds: float = 120
    uniquification_read_timeout_seconds: float = 300
    cleanup_outputs: bool = True
    keep_outputs: tuple[str, ...] = ()
    preparation_enabled: bool = False
    preparation_measurement_crs: str = 'EPSG:2950'
    preparation_source_crs: str | None = None
    preparation_source_crs_evidence: str | None = None
    preparation_coordinate_operation: str | None = None

    def __post_init__(self):
        for key in ('gis_cities_url', 'gis_validation_url'):
            object.__setattr__(self, key, http_url(getattr(self, key)))
        if not isinstance(self.fsa, str):
            raise ValueError('fsa must be a three-character Canadian FSA.')
        fsa = self.fsa.strip().upper()
        if not re.fullmatch(r'[A-Z][0-9][A-Z]', fsa):
            raise ValueError('fsa must be a three-character Canadian FSA.')
        object.__setattr__(self, 'fsa', fsa)
        if not isinstance(self.output_root, (str, Path)) or not str(self.output_root).strip():
            raise ValueError('output_root must be a nonblank path.')
        object.__setattr__(self, 'output_root', Path(self.output_root).resolve())
        for key in (
                'connect_timeout_seconds', 'preprocess_read_timeout_seconds',
                'download_read_timeout_seconds', 'uniquification_read_timeout_seconds'):
            value = getattr(self, key)
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or value <= 0):
                raise ValueError(f'{key} must be a positive finite number.')
        if type(self.cleanup_outputs) is not bool:
            raise ValueError('cleanup_outputs must be a boolean.')
        if (not isinstance(self.keep_outputs, (list, tuple))
                or any(not isinstance(k, str) or not k.strip() for k in self.keep_outputs)):
            raise ValueError('keep_outputs must be a list of nonblank output keys.')
        keys = tuple(dict.fromkeys(k.strip() for k in self.keep_outputs))
        if keys and not self.cleanup_outputs:
            raise ValueError('keep_outputs requires cleanup_outputs=true.')
        object.__setattr__(self, 'keep_outputs', keys)
        if type(self.preparation_enabled) is not bool:
            raise ValueError('preparation_enabled must be a boolean.')
        for key in ('preparation_measurement_crs', 'preparation_source_crs',
                    'preparation_source_crs_evidence', 'preparation_coordinate_operation'):
            value = getattr(self, key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f'{key} must be a nonblank string.')
        if self.preparation_measurement_crs is None:
            raise ValueError('preparation_measurement_crs is required.')
        if (self.preparation_source_crs is None) != (self.preparation_source_crs_evidence is None):
            raise ValueError('Source CRS override and independent verification evidence must be provided together.')

    @classmethod
    def from_file(cls, filename):
        path = Path(filename).resolve()
        with path.open(encoding='utf-8') as stream:
            values = json.load(stream)
        if not isinstance(values, dict):
            raise ValueError('Scenario configuration must be a JSON object.')
        if 'output_root' not in values or not isinstance(values['output_root'], str):
            raise ValueError('output_root must be a nonblank path.')
        if not values['output_root'].strip():
            raise ValueError('output_root must be a nonblank path.')
        values['output_root'] = path.parent / values['output_root']
        return cls(**values)

    def as_dict(self):
        result = asdict(self)
        result['output_root'] = str(self.output_root)
        return result

    def preprocessing_request(self):
        return {
            'mode': 'standardize', 'fsa': self.fsa,
            'cleanup_outputs': self.cleanup_outputs,
            'keep_outputs': list(self.keep_outputs),
        }

    def timeout(self, operation):
        return (self.connect_timeout_seconds,
                getattr(self, f'{operation}_read_timeout_seconds'))
