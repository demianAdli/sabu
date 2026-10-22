"""
Sabu project
jug_sim_buildings package
http_transport module
Stream HTTP responses with correlation and failure evidence.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import hashlib
import json
import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter


logger = logging.getLogger(__name__)


class TransportError(RuntimeError):
    """An HTTP exchange failed; any received bytes remain on disk."""


class HTTPTransport:
    """One attempt per exchange, including POSTs; never follow redirects."""

    def __init__(self):
        self.session = requests.Session()
        self.session.mount('http://', HTTPAdapter(max_retries=0))
        self.session.mount('https://', HTTPAdapter(max_retries=0))

    def close(self):
        self.session.close()

    def exchange(self, method, url, *, destination, metadata_path, run_id,
                 timeout, expected_status, body_path=None):
        metadata = {
            'method': method, 'url': url, 'request_id': run_id,
            'timeout_seconds': list(timeout), 'status': None, 'headers': {},
            'complete': False, 'size_bytes': 0,
        }
        digest = hashlib.sha256()
        primary_error = None
        headers = {'X-Request-ID': run_id, 'Accept-Encoding': 'identity'}
        headers['Accept'] = 'application/json, application/geo+json'
        if body_path is not None:
            headers['Content-Type'] = 'application/json'
        try:
            # Request files avoid an additional in-memory copy of large GeoJSON.
            with Path(destination).open('xb') as output:
                body = Path(body_path).open('rb') if body_path is not None else None
                try:
                    with self.session.request(
                            method, url, data=body, headers=headers,
                            timeout=timeout, stream=True, allow_redirects=False) as response:
                        metadata['status'] = response.status_code
                        metadata['headers'] = {
                            k.lower(): v for k, v in response.headers.items()
                            if k.lower() in {
                                'content-type', 'content-length', 'content-encoding',
                                'etag', 'last-modified', 'date', 'location',
                                'x-request-id', 'x-correlation-id',
                            }
                        }
                        for chunk in response.iter_content(chunk_size=65536):
                            if chunk:
                                output.write(chunk)
                                digest.update(chunk)
                                metadata['size_bytes'] += len(chunk)
                        length = response.headers.get('Content-Length')
                        encoding = response.headers.get('Content-Encoding', 'identity')
                        if length is not None and encoding.lower() == 'identity':
                            try:
                                expected_length = int(length)
                            except ValueError as exc:
                                raise TransportError('Invalid Content-Length.') from exc
                            if expected_length < 0 or expected_length != metadata['size_bytes']:
                                raise TransportError('Incomplete HTTP response: Content-Length mismatch.')
                        metadata['complete'] = True
                        if response.status_code != expected_status:
                            raise TransportError(
                                f'{method} {url} returned HTTP {response.status_code}; '
                                f'expected {expected_status}.')
                finally:
                    if body is not None:
                        body.close()
        except requests.RequestException as exc:
            primary_error = TransportError(f'{method} {url} failed: {exc}')
            raise primary_error from exc
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            metadata['sha256'] = digest.hexdigest()
            if primary_error is not None:
                metadata['error'] = {
                    'type': type(primary_error).__name__, 'message': str(primary_error)}
            try:
                Path(metadata_path).write_text(
                    json.dumps(metadata, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            except OSError:
                # A secondary evidence-writing failure must not replace HTTP errors.
                if primary_error is None:
                    raise
                logger.exception('http_evidence_write_failed', extra={'run_id': run_id})
        return metadata
