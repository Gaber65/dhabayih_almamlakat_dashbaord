from __future__ import annotations
import datetime as _dt
import decimal
import json
import uuid
from enum import Enum
from typing import Any, Optional, Union

class _JabinJSONEncoder(json.JSONEncoder):

    def default(self, o: Any) -> Any:
        if isinstance(o, _dt.datetime):
            return o.isoformat()
        if isinstance(o, _dt.date):
            return o.isoformat()
        if isinstance(o, _dt.time):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return str(o)
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, (set, frozenset)):
            return list(o)
        if isinstance(o, (bytes, bytearray)):
            try:
                return o.decode('utf-8')
            except UnicodeDecodeError:
                return repr(o)
        return super().default(o)

class JsonHelper:

    @staticmethod
    def dumps(obj: Any, ensure_ascii: bool=False, indent: Optional[int]=None, sort_keys: bool=False) -> str:
        return json.dumps(obj, cls=_JabinJSONEncoder, ensure_ascii=ensure_ascii, indent=indent, sort_keys=sort_keys)

    @staticmethod
    def loads(raw: Union[str, bytes, bytearray]) -> Any:
        return json.loads(raw)

    @staticmethod
    def dumps_pretty(obj: Any) -> str:
        return JsonHelper.dumps(obj, indent=2, sort_keys=True)