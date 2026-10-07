# M7 dependency inspection

Read-only; no personal records inspected.

MySQL: 8.4.11

## M7 tables
- programme_term_offering: absent
- class_section: absent
- class_batch: absent
- student_term_registration: absent
- course_offering: absent
- course_offering_section: absent
- student_course_registration: absent
- course_offering_section_student: absent

## academic_term
```sql
CREATE TABLE `academic_term` (
  `academic_term_id` int unsigned NOT NULL AUTO_INCREMENT,
  `term_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `term_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `term_type` varchar(6) NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `registration_start_date` date DEFAULT NULL,
  `registration_end_date` date DEFAULT NULL,
  `status` varchar(17) NOT NULL DEFAULT 'PLANNED',
  `academic_year_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`academic_term_id`),
  UNIQUE KEY `uq_term_code` (`academic_year_id`,`term_code`),
  KEY `calendar_term_status` (`status`,`start_date`),
  CONSTRAINT `academic_term_academic_year_id_b69e46f3_fk_academic_` FOREIGN KEY (`academic_year_id`) REFERENCES `academic_year` (`academic_year_id`),
  CONSTRAINT `chk_academic_term_status` CHECK ((`status` in (_utf8mb4'PLANNED',_utf8mb4'REGISTRATION_OPEN',_utf8mb4'ACTIVE',_utf8mb4'CLOSED'))),
  CONSTRAINT `chk_academic_term_type` CHECK ((`term_type` in (_utf8mb4'ODD',_utf8mb4'EVEN',_utf8mb4'SUMMER',_utf8mb4'ANNUAL',_utf8mb4'OTHER'))),
  CONSTRAINT `chk_term_dates` CHECK ((`end_date` >= `start_date`)),
  CONSTRAINT `chk_term_registration_dates` CHECK (((`registration_start_date` is null) or (`registration_end_date` is null) or (`registration_end_date` >= `registration_start_date`)))
) ENGINE=InnoDB AUTO_INCREMENT=241 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## programme
```sql
CREATE TABLE `programme` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `programme_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `programme_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `programme_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `award_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `programme_level` varchar(12) NOT NULL,
  `duration_semesters` tinyint unsigned NOT NULL,
  `maximum_duration_semesters` tinyint unsigned DEFAULT NULL,
  `department_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`programme_id`),
  UNIQUE KEY `programme_code` (`programme_code`),
  KEY `programme_department_id_62955943_fk_department_department_id` (`department_id`),
  CONSTRAINT `programme_department_id_62955943_fk_department_department_id` FOREIGN KEY (`department_id`) REFERENCES `department` (`department_id`),
  CONSTRAINT `chk_programme_duration` CHECK (((`duration_semesters` > 0) and ((`maximum_duration_semesters` is null) or (`maximum_duration_semesters` >= `duration_semesters`)))),
  CONSTRAINT `chk_programme_level` CHECK ((`programme_level` in (_utf8mb4'UG',_utf8mb4'PG',_utf8mb4'DIPLOMA',_utf8mb4'CERTIFICATE',_utf8mb4'DOCTORAL',_utf8mb4'OTHER'))),
  CONSTRAINT `programme_chk_1` CHECK ((`duration_semesters` >= 0)),
  CONSTRAINT `programme_chk_2` CHECK ((`maximum_duration_semesters` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## programme_specialization
```sql
CREATE TABLE `programme_specialization` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `specialization_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `specialization_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `specialization_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `programme_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`specialization_id`),
  UNIQUE KEY `uq_specialization_code` (`programme_id`,`specialization_code`),
  UNIQUE KEY `uq_specialization_programme` (`specialization_id`,`programme_id`),
  CONSTRAINT `programme_specializa_programme_id_faf44458_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## curriculum_scheme
```sql
CREATE TABLE `curriculum_scheme` (
  `curriculum_scheme_id` int unsigned NOT NULL AUTO_INCREMENT,
  `scheme_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `scheme_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `regulation_year` year NOT NULL,
  `total_credits` decimal(6,1) DEFAULT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  `status` varchar(7) NOT NULL DEFAULT 'DRAFT',
  `programme_id` smallint unsigned NOT NULL,
  `specialization_id` smallint unsigned DEFAULT NULL,
  PRIMARY KEY (`curriculum_scheme_id`),
  UNIQUE KEY `scheme_code` (`scheme_code`),
  UNIQUE KEY `uq_m6_scheme_programme` (`curriculum_scheme_id`,`programme_id`),
  KEY `scheme_effective_lookup` (`programme_id`,`specialization_id`,`status`,`effective_from`),
  KEY `curriculum_scheme_specialization_id_06b5dea8` (`specialization_id`),
  KEY `fk_scheme_specialization_programme` (`specialization_id`,`programme_id`),
  CONSTRAINT `curriculum_scheme_programme_id_b663bd0b_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`),
  CONSTRAINT `fk_scheme_specialization_programme` FOREIGN KEY (`specialization_id`, `programme_id`) REFERENCES `programme_specialization` (`specialization_id`, `programme_id`),
  CONSTRAINT `chk_scheme_effective_dates` CHECK (((`effective_to` is null) or (`effective_to` >= `effective_from`))),
  CONSTRAINT `chk_scheme_status` CHECK ((`status` in (_utf8mb4'DRAFT',_utf8mb4'ACTIVE',_utf8mb4'RETIRED'))),
  CONSTRAINT `chk_scheme_total_credits` CHECK (((`total_credits` is null) or (`total_credits` >= 0))),
  CONSTRAINT `curriculum_scheme_chk_1` CHECK ((`regulation_year` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## curriculum_course
```sql
CREATE TABLE `curriculum_course` (
  `curriculum_course_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `is_mandatory` tinyint(1) NOT NULL DEFAULT '1',
  `elective_group_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `display_order` smallint unsigned DEFAULT NULL,
  `internal_max_marks` decimal(6,2) NOT NULL DEFAULT '0.00',
  `external_max_marks` decimal(6,2) NOT NULL DEFAULT '0.00',
  `passing_marks` decimal(6,2) DEFAULT NULL,
  `exam_duration_minutes` smallint unsigned DEFAULT NULL,
  `course_id` int unsigned NOT NULL,
  `course_category_id` smallint unsigned NOT NULL,
  `semester_id` tinyint unsigned NOT NULL,
  `curriculum_scheme_id` int unsigned NOT NULL,
  PRIMARY KEY (`curriculum_course_id`),
  UNIQUE KEY `uq_curriculum_course` (`curriculum_scheme_id`,`semester_id`,`course_id`),
  UNIQUE KEY `uq_curriculum_display_order` (`curriculum_scheme_id`,`semester_id`,`display_order`),
  KEY `curriculum_course_course_id_7d898ba3_fk_course_catalog_course_id` (`course_id`),
  KEY `curriculum_course_course_category_id_12cf6d44_fk_course_ca` (`course_category_id`),
  KEY `curriculum_course_semester_id_4887864b_fk_semester_semester_id` (`semester_id`),
  CONSTRAINT `curriculum_course_course_category_id_12cf6d44_fk_course_ca` FOREIGN KEY (`course_category_id`) REFERENCES `course_category` (`course_category_id`),
  CONSTRAINT `curriculum_course_course_id_7d898ba3_fk_course_catalog_course_id` FOREIGN KEY (`course_id`) REFERENCES `course_catalog` (`course_id`),
  CONSTRAINT `curriculum_course_curriculum_scheme_id_c074a75f_fk_curriculu` FOREIGN KEY (`curriculum_scheme_id`) REFERENCES `curriculum_scheme` (`curriculum_scheme_id`),
  CONSTRAINT `curriculum_course_semester_id_4887864b_fk_semester_semester_id` FOREIGN KEY (`semester_id`) REFERENCES `semester` (`semester_id`),
  CONSTRAINT `chk_curriculum_elective` CHECK ((((`elective_group_code` is null) and (`is_mandatory` = 0x01)) or ((`elective_group_code` is not null) and (`is_mandatory` = 0x00) and (`elective_group_code` is not null)))),
  CONSTRAINT `chk_curriculum_marks` CHECK (((`external_max_marks` >= 0) and (`internal_max_marks` >= 0) and ((`passing_marks` is null) or ((`passing_marks` >= 0) and (`passing_marks` <= (`internal_max_marks` + `external_max_marks`)))))),
  CONSTRAINT `curriculum_course_chk_1` CHECK ((`display_order` >= 0)),
  CONSTRAINT `curriculum_course_chk_2` CHECK ((`exam_duration_minutes` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## semester
```sql
CREATE TABLE `semester` (
  `semester_id` tinyint unsigned NOT NULL AUTO_INCREMENT,
  `semester_number` tinyint unsigned NOT NULL,
  `semester_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`semester_id`),
  UNIQUE KEY `semester_number` (`semester_number`),
  UNIQUE KEY `semester_name` (`semester_name`),
  CONSTRAINT `chk_semester_number` CHECK ((`semester_number` > 0)),
  CONSTRAINT `semester_chk_1` CHECK ((`semester_number` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## room
```sql
CREATE TABLE `room` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `room_id` int unsigned NOT NULL AUTO_INCREMENT,
  `room_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `room_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `room_type` varchar(15) NOT NULL,
  `capacity` smallint unsigned DEFAULT NULL,
  `building_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`room_id`),
  UNIQUE KEY `uq_room_code` (`building_id`,`room_code`),
  CONSTRAINT `room_building_id_02c667dd_fk_building_building_id` FOREIGN KEY (`building_id`) REFERENCES `building` (`building_id`),
  CONSTRAINT `chk_room_capacity` CHECK (((`capacity` is null) or (`capacity` > 0))),
  CONSTRAINT `chk_room_type` CHECK ((`room_type` in (_utf8mb4'CLASSROOM',_utf8mb4'LAB',_utf8mb4'SEMINAR_HALL',_utf8mb4'AUDITORIUM',_utf8mb4'OFFICE',_utf8mb4'OTHER'))),
  CONSTRAINT `room_chk_1` CHECK ((`capacity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## course_catalog
```sql
CREATE TABLE `course_catalog` (
  `course_id` int unsigned NOT NULL AUTO_INCREMENT,
  `course_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `course_title` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `short_title` varchar(80) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `course_type` varchar(10) NOT NULL,
  `lecture_hours` decimal(4,1) NOT NULL DEFAULT '0.0',
  `tutorial_hours` decimal(4,1) NOT NULL DEFAULT '0.0',
  `practical_hours` decimal(4,1) NOT NULL DEFAULT '0.0',
  `self_study_hours` decimal(4,1) NOT NULL DEFAULT '0.0',
  `credits` decimal(4,1) NOT NULL DEFAULT '0.0',
  `effective_from` date DEFAULT NULL,
  `effective_to` date DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `owning_department_id` smallint unsigned NOT NULL,
  `course_category_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`course_id`),
  UNIQUE KEY `course_code` (`course_code`),
  KEY `catalog_department_active` (`owning_department_id`,`is_active`,`course_code`),
  KEY `course_catalog_course_category_id_ebc36fb7_fk_course_ca` (`course_category_id`),
  CONSTRAINT `course_catalog_course_category_id_ebc36fb7_fk_course_ca` FOREIGN KEY (`course_category_id`) REFERENCES `course_category` (`course_category_id`),
  CONSTRAINT `course_catalog_owning_department_id_cc99cdb7_fk_departmen` FOREIGN KEY (`owning_department_id`) REFERENCES `department` (`department_id`),
  CONSTRAINT `chk_catalog_course_type` CHECK ((`course_type` in (_utf8mb4'THEORY',_utf8mb4'LAB',_utf8mb4'THEORY_LAB',_utf8mb4'PROJECT',_utf8mb4'SEMINAR',_utf8mb4'INTERNSHIP',_utf8mb4'OTHER'))),
  CONSTRAINT `chk_course_effective_dates` CHECK (((`effective_from` is null) or (`effective_to` is null) or (`effective_to` >= `effective_from`))),
  CONSTRAINT `chk_course_nonnegative_values` CHECK (((`credits` >= 0) and (`lecture_hours` >= 0) and (`practical_hours` >= 0) and (`self_study_hours` >= 0) and (`tutorial_hours` >= 0)))
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## student_programme_enrolment
```sql
CREATE TABLE `student_programme_enrolment` (
  `version` bigint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `enrolment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `admission_date` date NOT NULL,
  `expected_completion_date` date DEFAULT NULL,
  `enrolment_status` varchar(11) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `admission_academic_year_id` smallint unsigned NOT NULL,
  `admission_category_id` smallint unsigned DEFAULT NULL,
  `admission_semester_id` tinyint unsigned NOT NULL,
  `application_id` bigint unsigned NOT NULL,
  `created_by_id` bigint NOT NULL,
  `curriculum_scheme_id` int unsigned NOT NULL,
  `programme_id` smallint unsigned NOT NULL,
  `specialization_id` smallint unsigned DEFAULT NULL,
  `student_id` bigint unsigned NOT NULL,
  `transfer_from_id` bigint unsigned DEFAULT NULL,
  `updated_by_id` bigint NOT NULL,
  PRIMARY KEY (`enrolment_id`),
  UNIQUE KEY `application_id` (`application_id`),
  UNIQUE KEY `uq_student_programme_enrolment` (`student_id`,`programme_id`,`admission_academic_year_id`),
  UNIQUE KEY `transfer_from_id` (`transfer_from_id`),
  KEY `ix_m6_enrolment_queue` (`programme_id`,`enrolment_status`,`admission_academic_year_id`),
  KEY `student_programme_en_admission_academic_y_c3480444_fk_academic_` (`admission_academic_year_id`),
  KEY `student_programme_en_admission_category_i_32e80b83_fk_admission` (`admission_category_id`),
  KEY `student_programme_en_admission_semester_i_def24d63_fk_semester_` (`admission_semester_id`),
  KEY `student_programme_en_created_by_id_1e17e3fb_fk_user_acco` (`created_by_id`),
  KEY `student_programme_en_updated_by_id_2fe8cde9_fk_user_acco` (`updated_by_id`),
  KEY `fk_m6_enrolment_specialization` (`specialization_id`,`programme_id`),
  KEY `fk_m6_conversion_student` (`application_id`,`student_id`),
  KEY `fk_m6_enrolment_scheme_programme` (`curriculum_scheme_id`,`programme_id`),
  CONSTRAINT `fk_m6_conversion_student` FOREIGN KEY (`application_id`, `student_id`) REFERENCES `admission_application` (`application_id`, `admitted_student_id`),
  CONSTRAINT `fk_m6_enrolment_scheme_programme` FOREIGN KEY (`curriculum_scheme_id`, `programme_id`) REFERENCES `curriculum_scheme` (`curriculum_scheme_id`, `programme_id`),
  CONSTRAINT `fk_m6_enrolment_specialization` FOREIGN KEY (`specialization_id`, `programme_id`) REFERENCES `programme_specialization` (`specialization_id`, `programme_id`),
  CONSTRAINT `student_programme_en_admission_academic_y_c3480444_fk_academic_` FOREIGN KEY (`admission_academic_year_id`) REFERENCES `academic_year` (`academic_year_id`),
  CONSTRAINT `student_programme_en_admission_category_i_32e80b83_fk_admission` FOREIGN KEY (`admission_category_id`) REFERENCES `admission_category` (`admission_category_id`),
  CONSTRAINT `student_programme_en_admission_semester_i_def24d63_fk_semester_` FOREIGN KEY (`admission_semester_id`) REFERENCES `semester` (`semester_id`),
  CONSTRAINT `student_programme_en_application_id_016351b6_fk_admission` FOREIGN KEY (`application_id`) REFERENCES `admission_application` (`application_id`),
  CONSTRAINT `student_programme_en_created_by_id_1e17e3fb_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `student_programme_en_curriculum_scheme_id_3c2b0d90_fk_curriculu` FOREIGN KEY (`curriculum_scheme_id`) REFERENCES `curriculum_scheme` (`curriculum_scheme_id`),
  CONSTRAINT `student_programme_en_programme_id_211a03c8_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`),
  CONSTRAINT `student_programme_en_specialization_id_4ea7341f_fk_programme` FOREIGN KEY (`specialization_id`) REFERENCES `programme_specialization` (`specialization_id`),
  CONSTRAINT `student_programme_en_student_id_39676e3a_fk_student_s` FOREIGN KEY (`student_id`) REFERENCES `student` (`student_id`),
  CONSTRAINT `student_programme_en_transfer_from_id_ea5324bc_fk_student_p` FOREIGN KEY (`transfer_from_id`) REFERENCES `student_programme_enrolment` (`enrolment_id`),
  CONSTRAINT `student_programme_en_updated_by_id_2fe8cde9_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `chk_m6_enrolment_completion` CHECK (((`expected_completion_date` is null) or (`expected_completion_date` >= `admission_date`))),
  CONSTRAINT `student_programme_enrolment_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## user_account
```sql
CREATE TABLE `user_account` (
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  `user_id` bigint NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```
