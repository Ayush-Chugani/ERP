# Calendar MySQL query plans

Temporary fixture: 80 years, 240 terms, 24 campus slots; all rows rolled back. Auto-increment gaps can remain. Plans are diagnostic samples, not production load benchmarks.

MySQL version: 8.4.11

## Current shared year
```text
-> Sort: academic_year.start_date DESC, academic_year.academic_year_id  (cost=0.35 rows=1)
    -> Index lookup on academic_year using calendar_year_status (status='ACTIVE')  (cost=0.35 rows=1)

```

## Open registration terms
```text
-> Sort: academic_term.start_date, academic_term.academic_term_id
    -> Stream results  (cost=0.827 rows=0.0167)
        -> Nested loop inner join  (cost=0.827 rows=0.0167)
            -> Filter: (academic_year.end_date >= DATE'2026-01-10')  (cost=0.71 rows=0.333)
                -> Index range scan on academic_year using calendar_year_status over (status = 'ACTIVE' AND start_date <= '2026-01-10'), with index condition: ((academic_year.`status` = 'ACTIVE') and (academic_year.start_date <= DATE'2026-01-10'))  (cost=0.71 rows=1)
            -> Filter: ((academic_term.`status` = 'REGISTRATION_OPEN') and ((academic_term.registration_start_date is null) or (academic_term.registration_start_date <= DATE'2026-01-10')) and ((academic_term.registration_end_date is null) or (academic_term.registration_end_date >= DATE'2026-01-10')))  (cost=0.265 rows=0.05)
                -> Index lookup on academic_term using uq_term_code (academic_year_id=academic_year.academic_year_id)  (cost=0.265 rows=1)

```

## Active terms
```text
-> Nested loop inner join  (cost=0.7 rows=0.05)
    -> Index lookup on academic_term using calendar_term_status (status='ACTIVE')  (cost=0.35 rows=1)
    -> Filter: (academic_year.`status` = 'ACTIVE')  (cost=0.255 rows=0.05)
        -> Single-row index lookup on academic_year using PRIMARY (academic_year_id=academic_term.academic_year_id)  (cost=0.255 rows=1)

```

## Campus slots
```text
-> Sort: time_slot.start_time, time_slot.end_time, time_slot.time_slot_id  (cost=2.65 rows=24)
    -> Filter: ((time_slot.is_active = 1) and (time_slot.campus_id = 1))  (cost=2.65 rows=24)
        -> Table scan on time_slot  (cost=2.65 rows=24)

```

## Term natural key
```text
-> Rows fetched before execution  (cost=0..0 rows=1)

```