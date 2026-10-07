from dataclasses import replace
from datetime import date, time
import pytest
from apps.teaching_timetable.intervals import (
    Meeting, shared_occurrence, collision_resources, occurrence_dates,
    assignment_covers_occurrences,
)


def meeting(**kwargs):
    original = Meeting(1,time(9),time(10),date(2026,9,1),date(2026,9,30),1,1,1)
    return replace(original,**kwargs)


def test_different_start_dates_still_collide():
    left=meeting()
    right=meeting(start=time(9,30),end=time(10,30),effective_from=date(2026,9,10))
    assert shared_occurrence(left,right)==date(2026,9,14)
    assert collision_resources(left,right)==('room','faculty','class_section')


def test_touching_clock_intervals_are_allowed():
    assert not collision_resources(meeting(),meeting(start=time(10),end=time(11)))


def test_date_overlap_without_shared_weekday_does_not_collide():
    assert shared_occurrence(meeting(),meeting(effective_from=date(2026,9,22),effective_to=date(2026,9,23))) is None


def test_inclusive_last_date_can_collide():
    assert shared_occurrence(meeting(effective_to=date(2026,9,21)),meeting(effective_from=date(2026,9,21)))==date(2026,9,21)


def test_different_batches_can_meet_with_distinct_resources():
    assert not collision_resources(meeting(batch_id=1),meeting(batch_id=2,room_id=2,employee_id=2))


def test_whole_section_conflicts_with_its_batch():
    assert collision_resources(meeting(),meeting(batch_id=2,room_id=2,employee_id=2))==('class_section',)


def test_null_room_does_not_hide_faculty_collision():
    assert collision_resources(meeting(room_id=None,section_id=2),meeting(room_id=None))==('faculty',)


@pytest.mark.parametrize('values',[{'weekday':0},{'start':time(10)},{'effective_to':date(2026,8,1)}])
def test_invalid_intervals_rejected(values):
    with pytest.raises(ValueError):
        meeting(**values)


def test_upper_date_boundary_without_matching_weekday():
    last = meeting(effective_from=date.max, effective_to=date.max,
                   weekday=date.max.isoweekday() % 7 + 1)
    assert shared_occurrence(last, last) is None
    assert occurrence_dates(last) == ()


def test_upper_date_boundary_with_matching_weekday():
    last = meeting(effective_from=date.max, effective_to=date.max,
                   weekday=date.max.isoweekday())
    assert shared_occurrence(last, last) == date.max
    assert occurrence_dates(last) == (date.max,)


def test_recurrence_includes_final_teaching_day():
    assert occurrence_dates(meeting(effective_to=date(2026, 9, 21))) == (
        date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21),
    )


def test_assignment_intersection_is_insufficient():
    assert not assignment_covers_occurrences(meeting(), date(2026, 9, 14), None)
    assert not assignment_covers_occurrences(
        meeting(), date(2026, 9, 1), date(2026, 9, 21),
    )


def test_assignment_only_needs_to_cover_actual_meeting_dates():
    assert assignment_covers_occurrences(
        meeting(), date(2026, 9, 7), date(2026, 9, 28),
    )


def test_empty_recurrence_is_not_valid_assignment_coverage():
    assert not assignment_covers_occurrences(
        meeting(effective_from=date(2026, 9, 1), effective_to=date(2026, 9, 2)),
        date(2026, 9, 1), None,
    )


def test_reversed_assignment_dates_rejected():
    with pytest.raises(ValueError):
        assignment_covers_occurrences(meeting(), date(2026, 9, 2), date(2026, 9, 1))
