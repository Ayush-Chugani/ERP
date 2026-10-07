"""Read-only typed public contracts. No unrestricted manager is exported."""
from dataclasses import dataclass
from datetime import date, time
from . import selectors


@dataclass(frozen=True)
class YearInfo:
    id: int
    code: str
    start: date
    end: date


@dataclass(frozen=True)
class TermInfo:
    id: int
    year_id: int
    code: str
    name: str
    start: date
    end: date
    status: str


@dataclass(frozen=True)
class SlotInfo:
    id: int
    campus_id: int
    code: str
    start: time
    end: time
    is_break: bool


def current_year(*, actor, institution_id) -> YearInfo | None:
    row = selectors.current_year(actor=actor, institution_id=institution_id)
    return YearInfo(row.pk, row.year_code, row.start_date, row.end_date) if row else None


def _term(row):
    return TermInfo(row.pk, row.academic_year_id, row.term_code, row.term_name, row.start_date, row.end_date, row.status)


def active_terms(*, actor, institution_id) -> tuple[TermInfo, ...]:
    return tuple(_term(row) for row in selectors.active_terms(actor=actor, institution_id=institution_id))


def registration_terms(*, actor, institution_id, on_date) -> tuple[TermInfo, ...]:
    return tuple(_term(row) for row in selectors.registration_terms(actor=actor, institution_id=institution_id, on_date=on_date))


def term_by_code(*, actor, institution_id, year_code, term_code) -> TermInfo | None:
    row = selectors.term_by_code(actor=actor, institution_id=institution_id, year_code=year_code, term_code=term_code)
    return _term(row) if row else None


def semesters(*, actor, institution_id) -> tuple[tuple[int, int, str], ...]:
    return tuple(selectors.semesters(actor=actor, institution_id=institution_id).values_list('pk', 'semester_number', 'semester_name'))


def campus_slots(*, actor, institution_id, campus_id) -> tuple[SlotInfo, ...]:
    return tuple(SlotInfo(row.pk, row.campus_id, row.slot_code, row.start_time, row.end_time, row.is_break)
                 for row in selectors.campus_slots(actor=actor, institution_id=institution_id, campus_id=campus_id))
