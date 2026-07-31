from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple
DEFAULT_PER_PAGE: int = 20
MAX_PER_PAGE: int = 100
MIN_PAGE: int = 1

@dataclass(frozen=True)
class PaginationMeta:
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool

    def to_dict(self) -> Dict[str, object]:
        return {'page': self.page, 'per_page': self.per_page, 'total_items': self.total_items, 'total_pages': self.total_pages, 'has_next': self.has_next, 'has_prev': self.has_prev}

class PaginationHelper:

    @staticmethod
    def _normalise(page: int, per_page: int) -> Tuple[int, int]:
        if page is None or page < MIN_PAGE:
            page = MIN_PAGE
        if per_page is None or per_page < 1:
            per_page = DEFAULT_PER_PAGE
        if per_page > MAX_PER_PAGE:
            per_page = MAX_PER_PAGE
        return (page, per_page)

    @staticmethod
    def build(total_items: int, page: int=1, per_page: int=DEFAULT_PER_PAGE) -> PaginationMeta:
        (page, per_page) = PaginationHelper._normalise(page, per_page)
        total_items = max(int(total_items), 0)
        total_pages = (total_items + per_page - 1) // per_page if per_page else 1
        if total_pages < 1:
            total_pages = 1
        has_next = page < total_pages
        has_prev = page > 1
        return PaginationMeta(page=page, per_page=per_page, total_items=total_items, total_pages=total_pages, has_next=has_next, has_prev=has_prev)

    @staticmethod
    def offset_limit(page: int, per_page: int) -> Tuple[int, int]:
        (page, per_page) = PaginationHelper._normalise(page, per_page)
        offset = (page - 1) * per_page
        return (offset, per_page)

    @staticmethod
    def meta_dict(total_items: int, page: int=1, per_page: int=DEFAULT_PER_PAGE) -> Dict[str, object]:
        return {'pagination': PaginationHelper.build(total_items, page, per_page).to_dict()}