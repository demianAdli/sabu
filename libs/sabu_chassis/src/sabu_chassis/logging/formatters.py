from __future__ import annotations

import json
import logging
import time
from typing import Any


class JsonFormatter(logging.Formatter):
    _BASE_RECORD_ATTRS = set(logging.makeLogRecord({}).__dict__.keys())
    _SKIP_EXTRA_ATTRS = {'message', 'asctime'}

    @classmethod
    def _to_jsonable(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, dict):
            return {
                str(k): cls._to_jsonable(v)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._to_jsonable(v) for v in value]
        return str(value)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(record.created)),
            'level': record.levelname,
            'service': getattr(record, 'service', None),
            'env': getattr(record, 'env', None),
            'logger': record.name,
            'request_id': getattr(record, 'request_id', '-'),
            'msg': record.getMessage(),
        }

        if record.exc_info:
            payload['exc_type'] = record.exc_info[0].__name__
            payload['exc_msg'] = str(record.exc_info[1])
            payload['stack'] = self.formatException(record.exc_info)

        extras = {
            key: self._to_jsonable(value)
            for key, value in record.__dict__.items()
            if key not in self._BASE_RECORD_ATTRS
            and key not in self._SKIP_EXTRA_ATTRS
        }
        payload.update(extras)

        return json.dumps(payload, ensure_ascii=False)
