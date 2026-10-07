# M10 local schema and query plans

Database: sims_reference_dev

## assessment_component

```sql

CREATE TABLE `assessment_component` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `assessment_component_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `component_code` varchar(30) NOT NULL,
  `component_name` varchar(100) NOT NULL,
  `component_type` varchar(20) NOT NULL,
  `maximum_marks` decimal(7,2) NOT NULL,
  `weightage_percent` decimal(5,2) DEFAULT NULL,
  `is_mandatory` tinyint(1) NOT NULL,
  `actor_id` bigint NOT NULL,
  `course_offering_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`assessment_component_id`),
  UNIQUE KEY `uq_assessment_component` (`course_offering_id`,`component_code`),
  UNIQUE KEY `uq_assessment_component_owner` (`assessment_component_id`,`course_offering_id`),
  KEY `assessment_component_actor_id_57c141aa_fk_user_account_user_id` (`actor_id`),
  CONSTRAINT `assessment_component_actor_id_57c141aa_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `assessment_component_course_offering_id_a6722a30_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`),
  CONSTRAINT `assessment_component_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `chk_m10_component_max` CHECK ((`maximum_marks` > 0)),
  CONSTRAINT `chk_m10_component_weight` CHECK (((`weightage_percent` is null) or ((`weightage_percent` >= 0) and (`weightage_percent` <= 100))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## assessment_event

```sql

CREATE TABLE `assessment_event` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `assessment_event_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `attempt_number` smallint unsigned NOT NULL,
  `event_number` smallint unsigned DEFAULT NULL,
  `event_title` varchar(150) NOT NULL,
  `assessment_date` date NOT NULL,
  `start_time` time(6) DEFAULT NULL,
  `end_time` time(6) DEFAULT NULL,
  `maximum_marks` decimal(7,2) NOT NULL,
  `reduced_maximum_marks` decimal(7,2) DEFAULT NULL,
  `details` longtext NOT NULL,
  `status` varchar(9) NOT NULL,
  `roster` json NOT NULL,
  `actor_id` bigint NOT NULL,
  `assessment_component_id` bigint unsigned NOT NULL,
  `course_offering_id` bigint unsigned NOT NULL,
  `policy_id` bigint NOT NULL,
  PRIMARY KEY (`assessment_event_id`),
  UNIQUE KEY `uq_assessment_event_owner` (`assessment_event_id`,`course_offering_id`),
  KEY `ix_m10_offering_events` (`course_offering_id`,`assessment_date`,`status`),
  KEY `assessment_event_actor_id_4d11f235_fk_user_account_user_id` (`actor_id`),
  KEY `assessment_event_policy_id_b4f889e1_fk_platform_m10_policy_id` (`policy_id`),
  KEY `fk_m10_event_component` (`assessment_component_id`,`course_offering_id`),
  CONSTRAINT `assessment_event_actor_id_4d11f235_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `assessment_event_assessment_component_3152bdf8_fk_assessmen` FOREIGN KEY (`assessment_component_id`) REFERENCES `assessment_component` (`assessment_component_id`),
  CONSTRAINT `assessment_event_course_offering_id_dc58e12d_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`),
  CONSTRAINT `assessment_event_policy_id_b4f889e1_fk_platform_m10_policy_id` FOREIGN KEY (`policy_id`) REFERENCES `platform_m10_policy` (`id`),
  CONSTRAINT `fk_m10_event_component` FOREIGN KEY (`assessment_component_id`, `course_offering_id`) REFERENCES `assessment_component` (`assessment_component_id`, `course_offering_id`),
  CONSTRAINT `assessment_event_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `assessment_event_chk_2` CHECK ((`attempt_number` >= 0)),
  CONSTRAINT `assessment_event_chk_3` CHECK ((`event_number` >= 0)),
  CONSTRAINT `chk_m10_event_attempt` CHECK (((`attempt_number` >= 1) and (`attempt_number` <= 255))),
  CONSTRAINT `chk_m10_event_marks` CHECK (((`maximum_marks` > 0) and ((`reduced_maximum_marks` is null) or ((`reduced_maximum_marks` > 0) and (`reduced_maximum_marks` <= `maximum_marks`))))),
  CONSTRAINT `chk_m10_event_status` CHECK ((`status` in (_utf8mb4'PLANNED',_utf8mb4'CONDUCTED',_utf8mb4'CANCELLED',_utf8mb4'PUBLISHED'))),
  CONSTRAINT `chk_m10_event_time` CHECK (((`start_time` is null) or (`end_time` is null) or (`end_time` > `start_time`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## student_assessment_mark

```sql

CREATE TABLE `student_assessment_mark` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `student_assessment_mark_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `attendance_status` varchar(11) NOT NULL,
  `marks_obtained` decimal(7,2) DEFAULT NULL,
  `reduced_marks` decimal(7,2) DEFAULT NULL,
  `remarks` varchar(500) NOT NULL,
  `evaluated_at` datetime(6) DEFAULT NULL,
  `actor_id` bigint NOT NULL,
  `assessment_event_id` bigint unsigned NOT NULL,
  `course_offering_id` bigint unsigned NOT NULL,
  `course_registration_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`student_assessment_mark_id`),
  UNIQUE KEY `uq_student_assessment` (`assessment_event_id`,`course_registration_id`),
  KEY `student_assessment_m_actor_id_473965ad_fk_user_acco` (`actor_id`),
  KEY `student_assessment_m_course_offering_id_7113739b_fk_course_of` (`course_offering_id`),
  KEY `fk_m10_mark_event` (`assessment_event_id`,`course_offering_id`),
  KEY `fk_m10_mark_registration` (`course_registration_id`,`course_offering_id`),
  CONSTRAINT `fk_m10_mark_event` FOREIGN KEY (`assessment_event_id`, `course_offering_id`) REFERENCES `assessment_event` (`assessment_event_id`, `course_offering_id`),
  CONSTRAINT `fk_m10_mark_registration` FOREIGN KEY (`course_registration_id`, `course_offering_id`) REFERENCES `student_course_registration` (`course_registration_id`, `course_offering_id`),
  CONSTRAINT `student_assessment_m_actor_id_473965ad_fk_user_acco` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `student_assessment_m_assessment_event_id_b51552dc_fk_assessmen` FOREIGN KEY (`assessment_event_id`) REFERENCES `assessment_event` (`assessment_event_id`),
  CONSTRAINT `student_assessment_m_course_offering_id_7113739b_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`),
  CONSTRAINT `student_assessment_m_course_registration__32ff3428_fk_student_c` FOREIGN KEY (`course_registration_id`) REFERENCES `student_course_registration` (`course_registration_id`),
  CONSTRAINT `chk_m10_mark_raw` CHECK (((`marks_obtained` is null) or (`marks_obtained` >= 0))),
  CONSTRAINT `chk_m10_mark_reduced` CHECK (((`reduced_marks` is null) or (`reduced_marks` >= 0))),
  CONSTRAINT `chk_m10_mark_status` CHECK ((`attendance_status` in (_utf8mb4'PRESENT',_utf8mb4'ABSENT',_utf8mb4'EXEMPTED',_utf8mb4'MALPRACTICE'))),
  CONSTRAINT `student_assessment_mark_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## grade_scale

```sql

CREATE TABLE `grade_scale` (
  `grade_scale_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `scale_name` varchar(100) NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `actor_id` bigint NOT NULL,
  `institution_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`grade_scale_id`),
  UNIQUE KEY `scale_name` (`scale_name`),
  KEY `grade_scale_actor_id_d7e96c46_fk_user_account_user_id` (`actor_id`),
  KEY `grade_scale_institution_id_1d17d268_fk_instituti` (`institution_id`),
  CONSTRAINT `grade_scale_actor_id_d7e96c46_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `grade_scale_institution_id_1d17d268_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `chk_m10_scale_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## grade_rule

```sql

CREATE TABLE `grade_rule` (
  `grade_rule_id` int unsigned NOT NULL AUTO_INCREMENT,
  `grade_letter` varchar(5) NOT NULL,
  `grade_point` decimal(4,2) NOT NULL,
  `minimum_percentage` decimal(5,2) NOT NULL,
  `maximum_percentage` decimal(5,2) NOT NULL,
  `result_status` varchar(8) NOT NULL,
  `grade_scale_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`grade_rule_id`),
  UNIQUE KEY `uq_grade_rule` (`grade_scale_id`,`grade_letter`),
  CONSTRAINT `grade_rule_grade_scale_id_39a312f0_fk_grade_scale_grade_scale_id` FOREIGN KEY (`grade_scale_id`) REFERENCES `grade_scale` (`grade_scale_id`),
  CONSTRAINT `chk_m10_grade_range` CHECK (((`grade_point` >= 0) and (`maximum_percentage` > `minimum_percentage`) and (`maximum_percentage` <= 100) and (`minimum_percentage` >= 0)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## student_course_result

```sql

CREATE TABLE `student_course_result` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `student_course_result_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `attempt_number` tinyint unsigned NOT NULL,
  `internal_marks` decimal(7,2) DEFAULT NULL,
  `external_marks` decimal(7,2) DEFAULT NULL,
  `total_marks` decimal(7,2) DEFAULT NULL,
  `grade_letter` varchar(5) NOT NULL,
  `grade_point` decimal(4,2) DEFAULT NULL,
  `credits_earned` decimal(4,1) NOT NULL,
  `result_status` varchar(10) NOT NULL,
  `result_date` date DEFAULT NULL,
  `remarks` varchar(500) NOT NULL,
  `evidence` json NOT NULL,
  `state` varchar(10) NOT NULL,
  `actor_id` bigint NOT NULL,
  `course_registration_id` bigint unsigned NOT NULL,
  `policy_id` bigint NOT NULL,
  `is_withheld` tinyint(1) NOT NULL,
  PRIMARY KEY (`student_course_result_id`),
  UNIQUE KEY `uq_course_result_attempt` (`course_registration_id`,`attempt_number`),
  KEY `student_course_result_actor_id_1550352f_fk_user_account_user_id` (`actor_id`),
  KEY `student_course_resul_policy_id_6138a661_fk_platform_` (`policy_id`),
  CONSTRAINT `student_course_resul_course_registration__12652408_fk_student_c` FOREIGN KEY (`course_registration_id`) REFERENCES `student_course_registration` (`course_registration_id`),
  CONSTRAINT `student_course_resul_policy_id_6138a661_fk_platform_` FOREIGN KEY (`policy_id`) REFERENCES `platform_m10_policy` (`id`),
  CONSTRAINT `student_course_result_actor_id_1550352f_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `chk_m10_course_result` CHECK (((`attempt_number` >= 1) and (`attempt_number` <= 255) and (`credits_earned` >= 0))),
  CONSTRAINT `chk_m10_course_state` CHECK ((`state` in (_utf8mb4'CALCULATED',_utf8mb4'PUBLISHED',_utf8mb4'WITHHELD'))),
  CONSTRAINT `chk_m10_course_status` CHECK ((`result_status` in (_utf8mb4'PASS',_utf8mb4'FAIL',_utf8mb4'ABSENT',_utf8mb4'WITHHELD',_utf8mb4'EXEMPTED',_utf8mb4'INCOMPLETE'))),
  CONSTRAINT `student_course_result_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `student_course_result_chk_2` CHECK ((`attempt_number` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## student_term_result

```sql

CREATE TABLE `student_term_result` (
  `version` bigint unsigned NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `student_term_result_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `credits_registered` decimal(6,1) NOT NULL,
  `credits_earned` decimal(6,1) NOT NULL,
  `sgpa` decimal(4,2) DEFAULT NULL,
  `cgpa` decimal(4,2) DEFAULT NULL,
  `result_status` varchar(10) NOT NULL,
  `published_at` datetime(6) DEFAULT NULL,
  `state` varchar(10) NOT NULL,
  `evidence` json NOT NULL,
  `actor_id` bigint NOT NULL,
  `term_registration_id` bigint unsigned NOT NULL,
  `is_withheld` tinyint(1) NOT NULL,
  PRIMARY KEY (`student_term_result_id`),
  UNIQUE KEY `term_registration_id` (`term_registration_id`),
  KEY `student_term_result_actor_id_ea60d1ed_fk_user_account_user_id` (`actor_id`),
  CONSTRAINT `student_term_result_actor_id_ea60d1ed_fk_user_account_user_id` FOREIGN KEY (`actor_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `student_term_result_term_registration_id_5b0e3b21_fk_student_t` FOREIGN KEY (`term_registration_id`) REFERENCES `student_term_registration` (`term_registration_id`),
  CONSTRAINT `chk_m10_term_credits` CHECK (((`credits_earned` >= 0) and (`credits_earned` <= `credits_registered`) and (`credits_registered` >= 0))),
  CONSTRAINT `chk_m10_term_state` CHECK ((`state` in (_utf8mb4'CALCULATED',_utf8mb4'PUBLISHED',_utf8mb4'WITHHELD'))),
  CONSTRAINT `chk_m10_term_status` CHECK ((`result_status` in (_utf8mb4'PASS',_utf8mb4'FAIL',_utf8mb4'PROMOTED',_utf8mb4'WITHHELD',_utf8mb4'INCOMPLETE'))),
  CONSTRAINT `student_term_result_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

```

## Query

```sql

SELECT * FROM assessment_event WHERE course_offering_id=1 AND status='CONDUCTED' ORDER BY assessment_date

```

```

((1, 'SIMPLE', 'assessment_event', None, 'ref', 'ix_m10_offering_events', 'ix_m10_offering_events', '8', 'const', 1, 100.0, 'Using index condition'),)

```

## Query

```sql

SELECT * FROM student_assessment_mark WHERE assessment_event_id=1

```

```

((1, 'SIMPLE', 'student_assessment_mark', None, 'ref', 'uq_student_assessment,fk_m10_mark_event', 'uq_student_assessment', '8', 'const', 1, 100.0, None),)

```

## Query

```sql

SELECT * FROM student_course_result WHERE course_registration_id=1 ORDER BY attempt_number

```

```

((1, 'SIMPLE', 'student_course_result', None, 'ref', 'uq_course_result_attempt', 'uq_course_result_attempt', '8', 'const', 1, 100.0, None),)

```

## Query

```sql

SELECT * FROM student_term_result WHERE term_registration_id=1

```

```

((1, 'SIMPLE', None, None, None, None, None, None, None, None, None, 'no matching row in const table'),)

```

Plans reflect the local empty development database, not production cardinality or latency acceptance.