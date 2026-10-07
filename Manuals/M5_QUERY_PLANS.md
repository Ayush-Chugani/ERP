# M5 MySQL query plans

Synthetic 1,000-student fixture, rolled back. No personal data or production load claim.

## Institution/status directory
```text
-> Limit: 25 row(s)  (cost=100 rows=25)
    -> Sort row IDs: student.student_number, limit input to 25 row(s) per chunk  (cost=100 rows=1000)
        -> Filter: ((student.student_status = 'APPLICANT') and (student.institution_id = 4))  (cost=100 rows=1000)
            -> Table scan on student  (cost=100 rows=1000)

```

## Institution identifier lookup
```text
-> Rows fetched before execution  (cost=0..0 rows=1)

```

## Scoped name search
```text
-> Limit: 25 row(s)  (cost=2.24 rows=2.78)
    -> Filter: ((student.institution_id = 4) and (student.display_name like '%100%'))  (cost=2.24 rows=2.78)
        -> Index scan on student using PRIMARY  (cost=2.24 rows=25)

```
