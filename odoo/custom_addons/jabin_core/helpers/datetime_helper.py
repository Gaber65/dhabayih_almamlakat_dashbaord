from __future__ import annotations
import datetime as _dt
from typing import Optional, Union
DEFAULT_TZ: str = 'UTC'

class DatetimeHelper:

    @staticmethod
    def now() -> _dt.datetime:
        return _dt.datetime.now(tz=_dt.timezone.utc)

    @staticmethod
    def today() -> _dt.date:
        return DatetimeHelper.now().date()

    @staticmethod
    def utcnow_naive() -> _dt.datetime:
        return _dt.datetime.utcnow()

    @staticmethod
    def parse_iso(value: str) -> _dt.datetime:
        parsed = _dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed

    @staticmethod
    def to_iso(value: _dt.datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=_dt.timezone.utc)
        return value.isoformat()

    @staticmethod
    def to_utc(value: _dt.datetime) -> _dt.datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=_dt.timezone.utc)
        return value.astimezone(_dt.timezone.utc)

    @staticmethod
    def to_timezone(value: _dt.datetime, tz_name: str) -> _dt.datetime:
        from zoneinfo import ZoneInfo
        if value.tzinfo is None:
            value = value.replace(tzinfo=_dt.timezone.utc)
        return value.astimezone(ZoneInfo(tz_name))

    @staticmethod
    def add_seconds(value: _dt.datetime, seconds: int) -> _dt.datetime:
        return value + _dt.timedelta(seconds=seconds)

    @staticmethod
    def add_minutes(value: _dt.datetime, minutes: int) -> _dt.datetime:
        return value + _dt.timedelta(minutes=minutes)

    @staticmethod
    def add_hours(value: _dt.datetime, hours: int) -> _dt.datetime:
        return value + _dt.timedelta(hours=hours)

    @staticmethod
    def add_days(value: _dt.datetime, days: int) -> _dt.datetime:
        return value + _dt.timedelta(days=days)

    @staticmethod
    def is_expired(value: _dt.datetime, ttl_seconds: int, reference: Optional[_dt.datetime]=None) -> bool:
        reference = reference or DatetimeHelper.now()
        value = DatetimeHelper.to_utc(value)
        reference = DatetimeHelper.to_utc(reference)
        return (reference - value).total_seconds() > ttl_seconds

    @staticmethod
    def start_of_day(value: _dt.date) -> _dt.datetime:
        return _dt.datetime.combine(value, _dt.time.min, tzinfo=_dt.timezone.utc)

    @staticmethod
    def end_of_day(value: _dt.date) -> _dt.datetime:
        return _dt.datetime.combine(value, _dt.time.max, tzinfo=_dt.timezone.utc)

    @staticmethod
    def humanize_delta(value: _dt.datetime, reference: Optional[_dt.datetime]=None) -> str:
        reference = reference or DatetimeHelper.now()
        value = DatetimeHelper.to_utc(value)
        reference = DatetimeHelper.to_utc(reference)
        delta = reference - value
        seconds = int(delta.total_seconds())
        if seconds < 0:
            return 'in the future'
        if seconds < 60:
            return f'{seconds}s ago'
        if seconds < 3600:
            return f'{seconds // 60}m ago'
        if seconds < 86400:
            return f'{seconds // 3600}h ago'
        return f'{seconds // 86400}d ago'