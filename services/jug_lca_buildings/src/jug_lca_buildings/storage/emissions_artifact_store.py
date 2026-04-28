"""
Sabu project
jug_lca_buildings package
Filesystem-backed cache for emissions results and exported reports.
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class EmissionsArtifactStore:
    """Persist emissions results and CSV exports on disk.

    Artifacts are keyed by a deterministic request hash.
    """

    CACHE_NAMESPACE = 'jug_lca_buildings_emissions_v1'

    def __init__(self, base_dir=None):
        configured_dir = base_dir or os.getenv(
            'JUG_LCA_ARTIFACTS_DIR',
            '.runtime/jug_lca_buildings',
        )
        self.base_dir = Path(configured_dir)

    def build_request_hash(self, request_city):
        payload = {
            'cache_namespace': self.CACHE_NAMESPACE,
            'request_city': request_city,
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def _artifact_dir(self, request_hash):
        return self.base_dir / request_hash

    def _json_path(self, request_hash):
        return self._artifact_dir(request_hash) / 'emissions.json'

    def _request_path(self, request_hash):
        return self._artifact_dir(request_hash) / 'request.json'

    def _csv_path(self, request_hash):
        return self._artifact_dir(request_hash) / 'emissions_report.csv'

    def _metadata_path(self, request_hash):
        return self._artifact_dir(request_hash) / 'metadata.json'

    def _ensure_dir(self, request_hash):
        artifact_dir = self._artifact_dir(request_hash)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    @staticmethod
    def _write_text_atomic(path, text):
        tmp_path = path.with_suffix(path.suffix + '.tmp')
        tmp_path.write_text(text, encoding='utf-8')
        tmp_path.replace(path)

    def _write_json_atomic(self, path, payload):
        self._write_text_atomic(
            path,
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        )

    def load_emissions_data(self, request_hash):
        path = self._json_path(request_hash)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding='utf-8'))

    def save_emissions_data(self, request_hash, request_city, emissions_data):
        self._ensure_dir(request_hash)
        self._write_json_atomic(self._request_path(request_hash), request_city)
        self._write_json_atomic(self._json_path(request_hash), emissions_data)
        self._write_json_atomic(
            self._metadata_path(request_hash),
            {
                'request_hash': request_hash,
                'cache_namespace': self.CACHE_NAMESPACE,
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'has_csv_report': self._csv_path(request_hash).exists(),
                'records': len(emissions_data or []),
            },
        )

    def load_csv_report(self, request_hash):
        path = self._csv_path(request_hash)
        if not path.exists():
            return None
        return path.read_text(encoding='utf-8')

    def save_csv_report(self, request_hash, csv_text):
        self._ensure_dir(request_hash)
        self._write_text_atomic(self._csv_path(request_hash), csv_text)

        metadata_path = self._metadata_path(request_hash)
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        else:
            metadata = {
                'request_hash': request_hash,
                'cache_namespace': self.CACHE_NAMESPACE,
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
            }
        metadata['has_csv_report'] = True
        metadata['csv_updated_at_utc'] = datetime.now(timezone.utc).isoformat()
        self._write_json_atomic(metadata_path, metadata)

    @staticmethod
    def build_csv_filename(request_hash):
        return f'jug_lca_buildings_emissions_report_{request_hash[:12]}.csv'
