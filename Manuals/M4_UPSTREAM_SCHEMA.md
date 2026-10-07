# M4 upstream schema verification

Read-only inspection of the configured development database.

MySQL version: 8.4.11

## organization.Institution
```sql
CREATE TABLE `institution` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `institution_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `institution_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `institution_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `legal_name` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `website_url` varchar(255) DEFAULT NULL,
  `email` varchar(254) DEFAULT NULL,
  `phone` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `university_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`institution_id`),
  UNIQUE KEY `institution_code` (`institution_code`),
  KEY `institution_university_id_386148bd_fk_university_university_id` (`university_id`),
  CONSTRAINT `institution_university_id_386148bd_fk_university_university_id` FOREIGN KEY (`university_id`) REFERENCES `university` (`university_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## organization.Campus
```sql
CREATE TABLE `campus` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `campus_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `campus_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `campus_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `address_line_1` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `address_line_2` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `city` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `postal_code` varchar(12) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `phone` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `email` varchar(254) DEFAULT NULL,
  `state_id` smallint unsigned DEFAULT NULL,
  `institution_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`campus_id`),
  UNIQUE KEY `uq_campus_code` (`institution_id`,`campus_code`),
  KEY `campus_state_id_5f399923_fk_state_state_id` (`state_id`),
  CONSTRAINT `campus_institution_id_34c3873e_fk_institution_institution_id` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `campus_state_id_5f399923_fk_state_state_id` FOREIGN KEY (`state_id`) REFERENCES `state` (`state_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## organization.Department
```sql
CREATE TABLE `department` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `department_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `department_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `department_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `department_type` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `campus_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`department_id`),
  UNIQUE KEY `uq_department_code` (`campus_id`,`department_code`),
  UNIQUE KEY `uq_department_id_campus` (`department_id`,`campus_id`),
  CONSTRAINT `department_campus_id_a01ac22d_fk_campus_campus_id` FOREIGN KEY (`campus_id`) REFERENCES `campus` (`campus_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## organization.Programme
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## organization.ProgrammeSpecialization
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

## academic_calendar.Semester
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

## Existing curriculum domain tables
- course_category: absent
- course_catalog: absent
- curriculum_scheme: absent
- curriculum_course: absent
- course_prerequisite: absent
