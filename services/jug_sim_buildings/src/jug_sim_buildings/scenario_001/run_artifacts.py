"""
Sabu project
jug_sim_buildings package
run_artifacts module
Preserve scenario artifacts and safely remove owned scratch files.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'size_bytes': Path(path).stat().st_size}


class RunArtifacts:
    """Own one new directory; cleanup only files explicitly tracked as temporary."""

    def __init__(self, output_root, run_id=None, *, fsa):
        if not isinstance(fsa, str) or not re.fullmatch(r'[A-Z][0-9][A-Z]', fsa):
            raise ValueError('fsa must be a normalized Canadian FSA.')
        self.fsa = fsa
        self.run_id = uuid4().hex if run_id is None else run_id
        if not isinstance(self.run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', self.run_id):
            raise ValueError('run_id must be 32 lowercase hexadecimal characters.')
        root = Path(output_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        fsa_root = root / fsa
        if fsa_root.resolve() != fsa_root:
            raise ValueError('Refusing a linked or redirected FSA directory.')
        fsa_root.mkdir(exist_ok=True)
        self.directory = fsa_root / self.run_id
        self.directory.mkdir()  # Existing runs are never reused or overwritten.
        self._temporary = set()
        for name in ('input', 'requests', 'responses', 'reports', 'evidence', 'tmp'):
            (self.directory / name).mkdir()

    def path(self, relative):
        relative = Path(relative)
        if relative.anchor or '..' in relative.parts:
            raise ValueError('Artifact path must stay within its run directory.')
        path = self.directory / relative
        # resolve detects symlinks and Windows junctions, including replaced parents.
        if (not path.is_relative_to(self.directory)
                or self.directory.resolve() != self.directory or path.resolve() != path):
            raise ValueError('Refusing a linked or redirected run artifact path.')
        return path

    def temporary(self, name):
        if Path(name).name != name or name in ('', '.', '..'):
            raise ValueError('Temporary filename must be a plain filename.')
        relative = Path('tmp') / name
        path = self.path(relative)
        self._temporary.add(relative)
        return path

    def write_json(self, relative, value):
        return self.write_text(
            relative, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')

    def write_text(self, relative, text):
        staging = self.temporary(f'{uuid4().hex}.tmp')
        with staging.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
        destination = self.path(relative)
        staging.replace(destination)
        self._temporary.discard(Path('tmp') / staging.name)
        return destination

    def write_json_lines(self, relative, values):
        staging = self.temporary(f'{uuid4().hex}.tmp')
        with staging.open('x', encoding='utf-8', newline='\n') as stream:
            for value in values:
                stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        staging.replace(self.path(relative))
        self._temporary.discard(Path('tmp') / staging.name)

    def promote_download(self):
        source = self.path('tmp/download.part')
        destination = self.path('input/standardized.geojson')
        if destination.exists():
            raise FileExistsError(destination)
        source.replace(destination)
        self._temporary.discard(Path('tmp/download.part'))
        return destination

    def cleanup(self, *, failed):
        """On failure quarantine partial downloads before deleting scratch; never recurse."""
        errors = []
        for relative in sorted(self._temporary):
            try:
                path = self.path(relative)
                if path.exists():
                    if failed and relative == Path('tmp/download.part') and path.stat().st_size:
                        destination = self.path('evidence/standardized.partial')
                        if destination.exists():
                            raise FileExistsError(destination)
                        path.replace(destination)
                    else:
                        path.unlink()
                self._temporary.discard(relative)
            except Exception as exc:
                errors.append({'path': str(relative), 'type': type(exc).__name__,
                               'message': str(exc)})
        # Leave the directory itself (and any untracked files) alone.
        return errors


class PreparationArtifacts(RunArtifacts):
    """Own one new preparation attempt without rewriting the parent run."""

    def __init__(self, run_directory):
        run_directory = Path(run_directory).resolve()
        parent = run_directory / 'preparation'
        if parent.resolve() != parent:
            raise ValueError('Refusing a linked preparation directory.')
        parent.mkdir(exist_ok=True)
        self.attempt_id = uuid4().hex
        self.directory = parent / self.attempt_id
        self.directory.mkdir()
        self._temporary = set()
        for name in ('tmp', 'evidence'):
            (self.directory / name).mkdir()

    def cleanup(self, *, failed):
        errors = []
        if failed:
            for name in ('geometry-wgs84.geojson', 'lca-final.geojson'):
                relative = Path('tmp') / name
                try:
                    source = self.path(relative)
                    if source.exists():
                        source.replace(self.path(f'evidence/{name}.partial'))
                        self._temporary.discard(relative)
                except Exception as exc:
                    errors.append({'path': str(relative), 'message': str(exc)})
                    # A failed quarantine must not lead to deletion of its evidence.
                    self._temporary.discard(relative)
        return errors + super().cleanup(failed=failed)
