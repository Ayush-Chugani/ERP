# M12 schema fidelity and local query plans

Canonical DDL is frozen in the initial migration. No extra domain columns or indexes are created.

## mentor_assignment

| Column | Django field | Nullable | Default | Choices | Relationship |

| --- | --- | --- | --- | --- | --- |

| mentor_assignment_id | UnsignedBigAutoField | False | none |  |  |

| student_id | ForeignKey | False | none |  | student |

| employee_id | ForeignKey | False | none |  | employee |

| start_date | DateField | False | none |  |  |

| end_date | DateField | True | none |  |  |

| assignment_status | NativeEnumField | False | ACTIVE | ['ACTIVE', 'COMPLETED', 'CANCELLED'] |  |

```sql

CREATE TABLE `mentor_assignment` (
  `mentor_assignment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `student_id` bigint unsigned NOT NULL,
  `employee_id` bigint unsigned NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `assignment_status` enum('ACTIVE','COMPLETED','CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ACTIVE',
  PRIMARY KEY (`mentor_assignment_id`),
  KEY `fk_mentor_assignment_student` (`student_id`),
  KEY `fk_mentor_assignment_employee` (`employee_id`),
  CONSTRAINT `fk_mentor_assignment_employee` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`),
  CONSTRAINT `fk_mentor_assignment_student` FOREIGN KEY (`student_id`) REFERENCES `student` (`student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## counselling_session

| Column | Django field | Nullable | Default | Choices | Relationship |

| --- | --- | --- | --- | --- | --- |

| counselling_session_id | UnsignedBigAutoField | False | none |  |  |

| mentor_assignment_id | ForeignKey | False | none |  | mentor_assignment |

| session_date | CanonicalDateTimeField | False | none |  |  |

| observations | CanonicalTextField | True | none |  |  |

| action_plan | CanonicalTextField | True | none |  |  |

| follow_up_date | DateField | True | none |  |  |

| session_status | NativeEnumField | False | COMPLETED | ['SCHEDULED', 'COMPLETED', 'CANCELLED', 'FOLLOW_UP_REQUIRED'] |  |

| confidentiality_level | NativeEnumField | False | RESTRICTED | ['NORMAL', 'RESTRICTED', 'HIGHLY_RESTRICTED'] |  |

```sql

CREATE TABLE `counselling_session` (
  `counselling_session_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `mentor_assignment_id` bigint unsigned NOT NULL,
  `session_date` datetime NOT NULL,
  `observations` text COLLATE utf8mb4_unicode_ci,
  `action_plan` text COLLATE utf8mb4_unicode_ci,
  `follow_up_date` date DEFAULT NULL,
  `session_status` enum('SCHEDULED','COMPLETED','CANCELLED','FOLLOW_UP_REQUIRED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'COMPLETED',
  `confidentiality_level` enum('NORMAL','RESTRICTED','HIGHLY_RESTRICTED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'RESTRICTED',
  PRIMARY KEY (`counselling_session_id`),
  KEY `fk_counselling_mentor_assignment` (`mentor_assignment_id`),
  CONSTRAINT `fk_counselling_mentor_assignment` FOREIGN KEY (`mentor_assignment_id`) REFERENCES `mentor_assignment` (`mentor_assignment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## grievance_category

| Column | Django field | Nullable | Default | Choices | Relationship |

| --- | --- | --- | --- | --- | --- |

| grievance_category_id | UnsignedAutoField | False | none |  |  |

| category_code | CharField | False | none |  |  |

| category_name | CharField | False | none |  |  |

| is_active | BooleanField | False | True |  |  |

```sql

CREATE TABLE `grievance_category` (
  `grievance_category_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `category_code` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`grievance_category_id`),
  UNIQUE KEY `category_code` (`category_code`),
  UNIQUE KEY `category_name` (`category_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## grievance

| Column | Django field | Nullable | Default | Choices | Relationship |

| --- | --- | --- | --- | --- | --- |

| grievance_id | UnsignedBigAutoField | False | none |  |  |

| grievance_number | CharField | False | none |  |  |

| student_id | ForeignKey | False | none |  | student |

| grievance_category_id | ForeignKey | False | none |  | grievance_category |

| department_id | ForeignKey | True | none |  | department |

| submitted_at | CanonicalDateTimeField | False | CurrentTimestamp() |  |  |

| subject | CharField | False | none |  |  |

| description | CanonicalTextField | False | none |  |  |

| priority | NativeEnumField | False | NORMAL | ['LOW', 'NORMAL', 'HIGH', 'URGENT'] |  |

| status | NativeEnumField | False | SUBMITTED | ['SUBMITTED', 'ASSIGNED', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED', 'CLOSED'] |  |

| resolved_at | CanonicalDateTimeField | True | none |  |  |

| resolution | CanonicalTextField | True | none |  |  |

```sql

CREATE TABLE `grievance` (
  `grievance_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `grievance_number` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `student_id` bigint unsigned NOT NULL,
  `grievance_category_id` smallint unsigned NOT NULL,
  `department_id` smallint unsigned DEFAULT NULL,
  `submitted_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `subject` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `priority` enum('LOW','NORMAL','HIGH','URGENT') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NORMAL',
  `status` enum('SUBMITTED','ASSIGNED','UNDER_REVIEW','RESOLVED','REJECTED','CLOSED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SUBMITTED',
  `resolved_at` datetime DEFAULT NULL,
  `resolution` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`grievance_id`),
  UNIQUE KEY `grievance_number` (`grievance_number`),
  KEY `fk_grievance_student` (`student_id`),
  KEY `fk_grievance_category` (`grievance_category_id`),
  KEY `fk_grievance_department` (`department_id`),
  CONSTRAINT `fk_grievance_category` FOREIGN KEY (`grievance_category_id`) REFERENCES `grievance_category` (`grievance_category_id`),
  CONSTRAINT `fk_grievance_department` FOREIGN KEY (`department_id`) REFERENCES `department` (`department_id`),
  CONSTRAINT `fk_grievance_student` FOREIGN KEY (`student_id`) REFERENCES `student` (`student_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## grievance_action

| Column | Django field | Nullable | Default | Choices | Relationship |

| --- | --- | --- | --- | --- | --- |

| grievance_action_id | UnsignedBigAutoField | False | none |  |  |

| grievance_id | ForeignKey | False | none |  | grievance |

| action_at | CanonicalDateTimeField | False | CurrentTimestamp() |  |  |

| action_type | CharField | False | none | ['SUBMITTED', 'ASSIGNED', 'REVIEW_STARTED', 'RESOLVED', 'REJECTED', 'CLOSED'] |  |

| action_notes | CanonicalTextField | True | none |  |  |

| new_status | CharField | True | none | ['SUBMITTED', 'ASSIGNED', 'UNDER_REVIEW', 'RESOLVED', 'REJECTED', 'CLOSED'] |  |

```sql

CREATE TABLE `grievance_action` (
  `grievance_action_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `grievance_id` bigint unsigned NOT NULL,
  `action_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `action_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action_notes` text COLLATE utf8mb4_unicode_ci,
  `new_status` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`grievance_action_id`),
  KEY `fk_grievance_action_grievance` (`grievance_id`),
  CONSTRAINT `fk_grievance_action_grievance` FOREIGN KEY (`grievance_id`) REFERENCES `grievance` (`grievance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

```sql

SELECT * FROM mentor_assignment WHERE student_id=1 AND assignment_status='ACTIVE'

```

```

((1, 'SIMPLE', 'mentor_assignment', None, 'ref', 'fk_mentor_assignment_student', 'fk_mentor_assignment_student', '8', 'const', 1, 100.0, 'Using where'),)

```

```sql

SELECT counselling_session_id,session_date,session_status FROM counselling_session WHERE mentor_assignment_id=1 ORDER BY session_date

```

```

((1, 'SIMPLE', 'counselling_session', None, 'ref', 'fk_counselling_mentor_assignment', 'fk_counselling_mentor_assignment', '8', 'const', 1, 100.0, 'Using filesort'),)

```

```sql

SELECT grievance_id,status,submitted_at FROM grievance WHERE department_id=1 AND status='SUBMITTED' ORDER BY submitted_at

```

```

((1, 'SIMPLE', 'grievance', None, 'ref', 'fk_grievance_department', 'fk_grievance_department', '3', 'const', 1, 100.0, 'Using where; Using filesort'),)

```

```sql

SELECT * FROM grievance_action WHERE grievance_id=1 ORDER BY action_at,grievance_action_id

```

```

((1, 'SIMPLE', 'grievance_action', None, 'ref', 'fk_grievance_action_grievance', 'fk_grievance_action_grievance', '8', 'const', 1, 100.0, 'Using filesort'),)

```

These plans describe the local development database only. Canonical foreign-key indexes are retained. Status/date composite indexes require a separately reviewed schema change and are deliberately not added.