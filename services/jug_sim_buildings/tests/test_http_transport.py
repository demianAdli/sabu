"""
Sabu project
jug_sim_buildings package
test_http_transport module
Verify controlled HTTP exchanges and preserved response evidence.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import requests
from requests.structures import CaseInsensitiveDict

from jug_sim_buildings.http_transport import HTTPTransport, TransportError


class ControlledResponse:
    """A streaming requests response stand-in; no sockets or GIS libraries."""

    def __init__(self, body=b'{}', status=200, headers=None, chunks=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict({'Content-Length': str(len(body)), **(headers or {})})
        self.chunks = [body] if chunks is None else chunks
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_content(self, chunk_size):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


class TestHTTPTransport(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.transport = HTTPTransport()
        self.addCleanup(self.transport.close)

    def exchange(self, response, *, method='GET', status=200, body_path=None):
        with patch.object(self.transport.session, 'request', side_effect=(
                response if isinstance(response, Exception) else None),
                return_value=response) as request:
            try:
                result = self.transport.exchange(
                    method, 'http://cities/artifacts/id/download',
                    destination=self.directory / 'response.body',
                    metadata_path=self.directory / 'response.http.json',
                    run_id='r' * 32, timeout=(3, 9), expected_status=status,
                    body_path=body_path)
            finally:
                self.last_request = request
        return result

    def test_stream_preserves_bytes_and_controls_requests(self):
        response = ControlledResponse(b'{"exact":  1}\n', headers={'X-Request-ID': 'upstream'})
        result = self.exchange(response)
        self.assertEqual((self.directory / 'response.body').read_bytes(), b'{"exact":  1}\n')
        self.assertTrue(result['complete'])
        self.assertEqual(result['headers']['x-request-id'], 'upstream')
        self.assertTrue(response.closed)
        kwargs = self.last_request.call_args.kwargs
        self.assertEqual(kwargs['timeout'], (3, 9))
        self.assertFalse(kwargs['allow_redirects'])
        self.assertTrue(kwargs['stream'])
        self.assertEqual(kwargs['headers']['X-Request-ID'], 'r' * 32)
        self.assertEqual(kwargs['headers']['Accept-Encoding'], 'identity')
        for scheme in ('http://', 'https://'):
            self.assertEqual(self.transport.session.get_adapter(scheme).max_retries.total, 0)

    def test_non_success_post_is_not_retried_and_body_is_saved(self):
        for status in (302, 307, 400, 409, 422, 500):
            with self.subTest(status=status), TemporaryDirectory() as directory:
                self.directory = Path(directory)
                with self.assertRaises(TransportError):
                    self.exchange(ControlledResponse(b'{"error":"failed"}', status),
                                  method='POST', status=201)
                self.assertEqual(self.last_request.call_count, 1)
                metadata = json.loads((self.directory / 'response.http.json').read_text())
                self.assertEqual(metadata['status'], status)
                self.assertTrue(metadata['complete'])
                self.assertEqual((self.directory / 'response.body').read_bytes(), b'{"error":"failed"}')

    def test_timeout_and_partial_stream_save_evidence_without_retry(self):
        for response, expected_bytes in (
                (requests.Timeout('connect timed out'), b''),
                (ControlledResponse(b'full', chunks=[b'pa', requests.ConnectionError('lost')]), b'pa'),
                (ControlledResponse(b'full', chunks=[b'pa']), b'pa')):
            with self.subTest(response=response), TemporaryDirectory() as directory:
                self.directory = Path(directory)
                with self.assertRaises(TransportError):
                    self.exchange(response)
                self.assertEqual(self.last_request.call_count, 1)
                self.assertEqual((self.directory / 'response.body').read_bytes(), expected_bytes)
                metadata = json.loads((self.directory / 'response.http.json').read_text())
                self.assertFalse(metadata['complete'])
                self.assertIn('error', metadata)

    def test_request_body_stream_is_closed_after_failure(self):
        body = self.directory / 'request.json'
        body.write_bytes(b'{"mode":"standardize"}')
        with self.assertRaises(TransportError):
            self.exchange(ControlledResponse(status=500), method='POST', status=201, body_path=body)
        self.assertTrue(self.last_request.call_args.kwargs['data'].closed)
        self.assertEqual(self.last_request.call_args.kwargs['headers']['Content-Type'], 'application/json')

    def test_secondary_metadata_error_does_not_hide_http_error(self):
        with self.assertLogs('jug_sim_buildings.http_transport', level='ERROR') as logs, \
                patch.object(Path, 'write_text', side_effect=PermissionError('metadata locked')):
            with self.assertRaisesRegex(TransportError, 'HTTP 500'):
                self.exchange(ControlledResponse(status=500))
        self.assertIn('http_evidence_write_failed', logs.output[0])
