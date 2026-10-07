# M4 MySQL query plans

Temporary fixture: 100 courses, 20 schemes, 100 mappings and 99 prerequisite edges. All fixture writes roll back; auto-increment gaps may remain. This is plan evidence, not a production load benchmark.

MySQL: 8.4.11

## Scoped active course list
```text
-> Sort: course_catalog.course_code, course_catalog.course_id  (cost=10.2 rows=100)
    -> Filter: ((course_catalog.owning_department_id = 1) and (course_catalog.is_active = 1))  (cost=10.2 rows=100)
        -> Table scan on course_catalog  (cost=10.2 rows=100)

```

## Current scheme candidates
```text
-> Index range scan on curriculum_scheme using scheme_effective_lookup over (programme_id = 1 AND specialization_id = NULL AND status = 'ACTIVE' AND effective_from <= '2019-06-01'), with index condition: ((curriculum_scheme.`status` = 'ACTIVE') and (curriculum_scheme.programme_id = 1) and (curriculum_scheme.effective_from <= DATE'2019-06-01') and (curriculum_scheme.specialization_id is null))  (cost=0.71 rows=1)

```

## Semester composition
```text
-> Sort: curriculum_course.display_order, curriculum_course.curriculum_course_id
    -> Stream results  (cost=1.19 rows=0.1)
        -> Nested loop inner join  (cost=1.19 rows=0.1)
            -> Nested loop inner join  (cost=1.15 rows=0.1)
                -> Table scan on course_category  (cost=0.45 rows=2)
                -> Filter: ((curriculum_course.semester_id = 1) and (curriculum_course.curriculum_scheme_id = 20))  (cost=0.253 rows=0.05)
                    -> Index lookup on curriculum_course using curriculum_course_course_category_id_12cf6d44_fk_course_ca (course_category_id=course_category.course_category_id)  (cost=0.253 rows=1)
            -> Single-row index lookup on course_catalog using PRIMARY (course_id=curriculum_course.course_id)  (cost=1.25 rows=1)

```

## Prerequisite lookup
```text
-> Nested loop inner join  (cost=0.7 rows=1)
    -> Index lookup on course_prerequisite using PRIMARY (course_id=100)  (cost=0.35 rows=1)
    -> Single-row index lookup on T3 using PRIMARY (course_id=course_prerequisite.prerequisite_course_id)  (cost=0.35 rows=1)

```
