from __future__ import annotations

import logging
import os
import re

from .context import get_request_id


_ANSI_RE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')


class ContextFilter(logging.Filter):
    def __init__(
        self,
        service: str | None = None,
        env: str | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._env = env

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.service = self._service or os.getenv('LOG_SERVICE', 'jugs-service')
        record.env = self._env or os.getenv('LOG_ENV', 'dev')
        return True


class StripANSIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = _ANSI_RE.sub('', message)

        record.msg = cleaned
        record.args = ()
        return True
