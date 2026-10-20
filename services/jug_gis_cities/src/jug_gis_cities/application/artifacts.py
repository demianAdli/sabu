"""Persistent registrations and immutable copies of generated GeoJSON files."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sabu_chassis.logging import get_logger

from .batch_jobs import DEFAULT_JOB_STORE_PATH, JOB_STORE_PATH_ENV


logger = get_logger(__name__)
ARTIFACT_DIR_ENV = 'JUG_GIS_CITIES_ARTIFACT_DIR'
_ID_PATTERN = re.compile(r'^[0-9a-f]{32}$')


class ArtifactError(RuntimeError):
    """An artifact could not be registered or read."""


class ArtifactNotFoundError(ArtifactError):
    """The ID has never been registered in this store."""


class ArtifactUnavailableError(ArtifactError):
    """A registered artifact no longer has an available stored copy."""


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    component_name: str
    fsa: str | None
    created_at: str
    size_bytes: int
    sha256: str


class ArtifactStore:
    """Publish files before registrations; never update an existing ID.

    A crash before the database commit can leave an unregistered directory.
    Such files are never served. Neither workflow cleanup nor worker recovery
    deletes registrations or stored copies.
    """

    def __init__(self, directory=None):
        job_path = Path(os.getenv(JOB_STORE_PATH_ENV, DEFAULT_JOB_STORE_PATH))
        self.directory = Path(
            directory or os.getenv(ARTIFACT_DIR_ENV)
            or job_path.absolute().parent / 'jug_gis_cities_artifacts'
        ).resolve()
        self.database_path = self.directory / 'registry.sqlite3'
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute('PRAGMA journal_mode = WAL')
                connection.execute('''
                    CREATE TABLE IF NOT EXISTS artifacts (
                        artifact_id TEXT PRIMARY KEY,
                        component_name TEXT NOT NULL,
                        fsa TEXT,
                        created_at TEXT NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        sha256 TEXT NOT NULL
                    )
                ''')
        except (OSError, sqlite3.Error) as exc:
            raise ArtifactError('Artifact store is unavailable.') from exc

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            with connection:
                yield connection
        finally:
            connection.close()

    def register(self, source_path, *, component_name, fsa=None):
        """Copy only a server-generated output supplied by the application."""
        artifact_directory = None
        try:
            # Exclusive directory creation prevents even an ID collision from
            # replacing an older file. There is deliberately no update/upsert.
            for _ in range(3):
                artifact_id = uuid.uuid4().hex
                candidate = self.directory / artifact_id
                try:
                    candidate.mkdir()
                except FileExistsError:
                    continue
                artifact_directory = candidate
                break
            if artifact_directory is None:
                raise ArtifactError('Could not allocate a new artifact ID.')

            temporary_path = artifact_directory / 'output.part'
            digest = hashlib.sha256()
            size_bytes = 0
            with open(source_path, 'rb') as source, temporary_path.open('xb') as target:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ArtifactError('Generated artifact must be a file.')
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
                target.flush()
                os.fsync(target.fileno())
            temporary_path.rename(artifact_directory / 'output.geojson')
            artifact = Artifact(
                artifact_id=artifact_id,
                component_name=component_name,
                fsa=fsa,
                created_at=datetime.now(timezone.utc).isoformat(),
                size_bytes=size_bytes,
                sha256=digest.hexdigest())
            with self._connect() as connection:
                connection.execute(
                    'INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)',
                    (artifact.artifact_id, artifact.component_name,
                     artifact.fsa, artifact.created_at, artifact.size_bytes,
                     artifact.sha256))
        except (OSError, sqlite3.Error, ArtifactError, TypeError) as exc:
            # Remove only this attempt's files. Crash leftovers remain
            # unregistered and cannot be downloaded through this API.
            if artifact_directory is not None:
                try:
                    for name in ('output.part', 'output.geojson'):
                        (artifact_directory / name).unlink(missing_ok=True)
                    artifact_directory.rmdir()
                except OSError:
                    logger.warning('Could not remove incomplete artifact copy.')
            raise ArtifactError('Failed to register generated artifact.') from exc
        logger.info(
            'Registered standardized artifact. ArtifactId=%s Component=%s FSA=%s',
            artifact.artifact_id, component_name, fsa)
        return artifact

    def get(self, artifact_id):
        if not isinstance(artifact_id, str) or not _ID_PATTERN.fullmatch(artifact_id):
            raise ArtifactNotFoundError('Artifact not found.')
        try:
            with self._connect() as connection:
                row = connection.execute(
                    'SELECT * FROM artifacts WHERE artifact_id = ?',
                    (artifact_id,)).fetchone()
        except sqlite3.Error as exc:
            raise ArtifactError('Artifact store is unavailable.') from exc
        if row is None:
            raise ArtifactNotFoundError('Artifact not found.')
        return Artifact(**dict(row))

    def open_download(self, artifact_id):
        """Return an opened registered file, never a caller-selected path."""
        artifact = self.get(artifact_id)
        parent = self.directory / artifact.artifact_id
        path = parent / 'output.geojson'
        stream = None
        try:
            if (parent.is_symlink() or path.is_symlink()
                    or path.resolve() != path):
                raise ArtifactUnavailableError('Artifact is unavailable.')
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0)
            flags |= getattr(os, 'O_NOFOLLOW', 0)
            stream = os.fdopen(os.open(path, flags), 'rb')
            file_stat = os.fstat(stream.fileno())
            if (not stat.S_ISREG(file_stat.st_mode)
                    or file_stat.st_size != artifact.size_bytes):
                raise ArtifactUnavailableError('Artifact is unavailable.')
        except (FileNotFoundError, NotADirectoryError, ArtifactUnavailableError) as exc:
            if stream is not None:
                stream.close()
            raise ArtifactUnavailableError('Artifact is unavailable.') from exc
        except OSError as exc:
            if stream is not None:
                stream.close()
            raise ArtifactError('Failed to read artifact.') from exc
        return artifact, stream


def get_artifact_store():
    """Use the same environment configuration in HTTP and spawned workers."""
    return ArtifactStore()
