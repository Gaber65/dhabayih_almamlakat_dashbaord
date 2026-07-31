from __future__ import annotations
import re
import unicodedata
from typing import Optional

class StringHelper:

    @staticmethod
    def slugify(value: str, separator: str='-') -> str:
        if not value:
            return ''
        normalised = unicodedata.normalize('NFKD', value)
        ascii_only = normalised.encode('ascii', 'ignore').decode('ascii')
        ascii_only = ascii_only.lower().strip()
        slug = re.sub('[^a-z0-9]+', separator, ascii_only)
        slug = re.sub(f'{re.escape(separator)}+', separator, slug)
        return slug.strip(separator)

    @staticmethod
    def truncate(value: str, max_length: int=100, suffix: str='...') -> str:
        if not value:
            return ''
        if len(value) <= max_length:
            return value
        if max_length <= len(suffix):
            return suffix[:max_length]
        return value[:max_length - len(suffix)] + suffix

    @staticmethod
    def snake_to_camel(value: str) -> str:
        if not value:
            return ''
        parts = value.split('_')
        return parts[0] + ''.join((p.capitalize() for p in parts[1:]))

    @staticmethod
    def camel_to_snake(value: str) -> str:
        if not value:
            return ''
        s1 = re.sub('(.)([A-Z][a-z]+)', '\\1_\\2', value)
        s2 = re.sub('([a-z0-9])([A-Z])', '\\1_\\2', s1)
        return s2.lower()

    @staticmethod
    def normalise_whitespace(value: Optional[str]) -> str:
        if not value:
            return ''
        return re.sub('\\s+', ' ', value).strip()

    @staticmethod
    def mask_email(value: str) -> str:
        if not value or '@' not in value:
            return StringHelper.mask(value or '')
        (local, domain) = value.split('@', 1)
        masked_local = StringHelper._mask_segment(local, reveal=1)
        if '.' in domain:
            (dname, dsuffix) = domain.rsplit('.', 1)
            masked_domain = f'{StringHelper._mask_segment(dname, reveal=1)}.{dsuffix}'
        else:
            masked_domain = StringHelper._mask_segment(domain, reveal=1)
        return f'{masked_local}@{masked_domain}'

    @staticmethod
    def mask(value: str, reveal: int=0) -> str:
        if not value:
            return ''
        if reveal <= 0:
            return '*' * len(value)
        if reveal >= len(value):
            return value
        return value[:reveal] + '*' * (len(value) - reveal)

    @staticmethod
    def _mask_segment(segment: str, reveal: int=1) -> str:
        if not segment:
            return ''
        if len(segment) <= reveal:
            return segment
        return segment[:reveal] + '*' * (len(segment) - reveal)

    @staticmethod
    def is_blank(value: Optional[str]) -> bool:
        return value is None or not value.strip()

    @staticmethod
    def default_if_blank(value: Optional[str], default: str='') -> str:
        if StringHelper.is_blank(value):
            return default
        return value.strip()