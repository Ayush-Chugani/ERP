"""Pure scheduling primitives; authorization and transactional locking live above them.

Clock intervals are half-open. Effective dates are inclusive and must be bounded
by the academic term before calling these functions. Weekdays use ISO 1..7.
"""
from dataclasses import dataclass
from datetime import date, time, timedelta


@dataclass(frozen=True)
class Meeting:
    weekday: int
    start: time
    end: time
    effective_from: date
    effective_to: date
    room_id: int | None
    employee_id: int | None
    section_id: int
    batch_id: int | None = None

    def __post_init__(self):
        if not 1 <= self.weekday <= 7:
            raise ValueError('Weekday must be 1..7.')
        if self.end <= self.start:
            raise ValueError('Clock interval must have positive duration; overnight slots are unsupported.')
        if self.effective_to < self.effective_from:
            raise ValueError('Effective end cannot precede start.')


def shared_occurrence(left: Meeting, right: Meeting) -> date | None:
    if left.weekday != right.weekday or left.start >= right.end or right.start >= left.end:
        return None
    first = max(left.effective_from, right.effective_from)
    last = min(left.effective_to, right.effective_to)
    offset = (left.weekday - first.isoweekday()) % 7
    # Compare before adding so date.max and disjoint ranges cannot overflow.
    if (last - first).days < offset:
        return None
    return first + timedelta(days=offset)


def occurrence_dates(meeting: Meeting) -> tuple[date, ...]:
    """Expand an already term-bounded recurrence, including its final date."""
    offset = (meeting.weekday - meeting.effective_from.isoweekday()) % 7
    span = (meeting.effective_to - meeting.effective_from).days
    return tuple(
        meeting.effective_from + timedelta(days=day)
        for day in range(offset, span + 1, 7)
    )


def assignment_covers_occurrences(
    meeting: Meeting, start: date, end: date | None,
) -> bool:
    """Check every teaching date, not just intersection with assignment dates.

    This is date coverage only; the caller must check status, ownership,
    eligibility and authorization. An empty recurrence cannot be scheduled.
    """
    if end is not None and end < start:
        raise ValueError('Assignment end cannot precede start.')
    dates = occurrence_dates(meeting)
    return bool(dates) and start <= dates[0] and (end is None or dates[-1] <= end)


def collision_resources(left: Meeting, right: Meeting) -> tuple[str, ...]:
    if shared_occurrence(left, right) is None:
        return ()
    resources = []
    if left.room_id is not None and left.room_id == right.room_id:
        resources.append('room')
    if left.employee_id is not None and left.employee_id == right.employee_id:
        resources.append('faculty')
    if left.section_id == right.section_id:
        if left.batch_id is None or right.batch_id is None:
            resources.append('class_section')
        elif left.batch_id == right.batch_id:
            resources.append('class_batch')
    return tuple(resources)
