# M6 live schema inspection

Read-only; no personal records inspected.

MySQL: 8.4.11

## Module6 target tables
- admission_applicant: absent
- admission_application: absent
- student_programme_enrolment: absent
- enrolment_status_history: absent

## student
```sql
CREATE TABLE `student` (
  `student_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `student_number` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `university_seat_number` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `first_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `middle_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `display_name` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `date_of_birth` date DEFAULT NULL,
  `primary_email` varchar(254) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `primary_phone` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `photo_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `admission_date` date DEFAULT NULL,
  `student_status` varchar(9) NOT NULL DEFAULT 'APPLICANT',
  `notes` longtext,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `blood_group_id` tinyint unsigned DEFAULT NULL,
  `campus_id` smallint unsigned DEFAULT NULL,
  `caste_id` int unsigned DEFAULT NULL,
  `department_id` smallint unsigned DEFAULT NULL,
  `gender_id` tinyint unsigned DEFAULT NULL,
  `institution_id` smallint unsigned NOT NULL,
  `nationality_country_id` smallint unsigned DEFAULT NULL,
  `religion_id` smallint unsigned DEFAULT NULL,
  `social_category_id` smallint unsigned DEFAULT NULL,
  `sub_caste_id` int unsigned DEFAULT NULL,
  PRIMARY KEY (`student_id`),
  UNIQUE KEY `student_number` (`student_number`),
  UNIQUE KEY `university_seat_number` (`university_seat_number`),
  UNIQUE KEY `uq_student_primary_email` (`primary_email`),
  KEY `m5_student_scope` (`institution_id`,`student_status`,`student_number`),
  KEY `student_blood_group_id_e0ceaa42_fk_blood_group_blood_group_id` (`blood_group_id`),
  KEY `student_campus_id_8a3f0fd0_fk_campus_campus_id` (`campus_id`),
  KEY `student_caste_id_93c0a86b_fk_caste_caste_id` (`caste_id`),
  KEY `student_department_id_20004f3d_fk_department_department_id` (`department_id`),
  KEY `student_gender_id_b11172d7_fk_gender_gender_id` (`gender_id`),
  KEY `student_nationality_country_id_a0eb75e2_fk_country_country_id` (`nationality_country_id`),
  KEY `student_religion_id_bc3ccf97_fk_religion_religion_id` (`religion_id`),
  KEY `student_social_category_id_f2745847_fk_social_ca` (`social_category_id`),
  KEY `student_sub_caste_id_447b1b68_fk_sub_caste_sub_caste_id` (`sub_caste_id`),
  CONSTRAINT `student_blood_group_id_e0ceaa42_fk_blood_group_blood_group_id` FOREIGN KEY (`blood_group_id`) REFERENCES `blood_group` (`blood_group_id`),
  CONSTRAINT `student_campus_id_8a3f0fd0_fk_campus_campus_id` FOREIGN KEY (`campus_id`) REFERENCES `campus` (`campus_id`),
  CONSTRAINT `student_caste_id_93c0a86b_fk_caste_caste_id` FOREIGN KEY (`caste_id`) REFERENCES `caste` (`caste_id`),
  CONSTRAINT `student_department_id_20004f3d_fk_department_department_id` FOREIGN KEY (`department_id`) REFERENCES `department` (`department_id`),
  CONSTRAINT `student_gender_id_b11172d7_fk_gender_gender_id` FOREIGN KEY (`gender_id`) REFERENCES `gender` (`gender_id`),
  CONSTRAINT `student_institution_id_e66af43f_fk_institution_institution_id` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `student_nationality_country_id_a0eb75e2_fk_country_country_id` FOREIGN KEY (`nationality_country_id`) REFERENCES `country` (`country_id`),
  CONSTRAINT `student_religion_id_bc3ccf97_fk_religion_religion_id` FOREIGN KEY (`religion_id`) REFERENCES `religion` (`religion_id`),
  CONSTRAINT `student_social_category_id_f2745847_fk_social_ca` FOREIGN KEY (`social_category_id`) REFERENCES `social_category` (`social_category_id`),
  CONSTRAINT `student_sub_caste_id_447b1b68_fk_sub_caste_sub_caste_id` FOREIGN KEY (`sub_caste_id`) REFERENCES `sub_caste` (`sub_caste_id`),
  CONSTRAINT `chk_m5_student_student_statu` CHECK ((`student_status` in (_utf8mb4'APPLICANT',_utf8mb4'ACTIVE',_utf8mb4'SUSPENDED',_utf8mb4'WITHDRAWN',_utf8mb4'COMPLETED',_utf8mb4'ALUMNUS',_utf8mb4'DECEASED')))
) ENGINE=InnoDB AUTO_INCREMENT=1001 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
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

## academic_year
```sql
CREATE TABLE `academic_year` (
  `academic_year_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `year_code` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `status` varchar(7) NOT NULL DEFAULT 'PLANNED',
  PRIMARY KEY (`academic_year_id`),
  UNIQUE KEY `year_code` (`year_code`),
  KEY `calendar_year_status` (`status`,`start_date`),
  CONSTRAINT `chk_academic_year_dates` CHECK ((`end_date` > `start_date`)),
  CONSTRAINT `chk_academic_year_status` CHECK ((`status` in (_utf8mb4'PLANNED',_utf8mb4'ACTIVE',_utf8mb4'CLOSED')))
) ENGINE=InnoDB AUTO_INCREMENT=82 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## admission_category
```sql
CREATE TABLE `admission_category` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `admission_category_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `category_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `category_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `description` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  PRIMARY KEY (`admission_category_id`),
  UNIQUE KEY `category_code` (`category_code`),
  UNIQUE KEY `category_name` (`category_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## gender
```sql
CREATE TABLE `gender` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `gender_id` tinyint unsigned NOT NULL AUTO_INCREMENT,
  `gender_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `gender_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  PRIMARY KEY (`gender_id`),
  UNIQUE KEY `gender_code` (`gender_code`),
  UNIQUE KEY `gender_name` (`gender_name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## country
```sql
CREATE TABLE `country` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `country_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `iso_code` char(2) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `country_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  PRIMARY KEY (`country_id`),
  UNIQUE KEY `iso_code` (`iso_code`),
  UNIQUE KEY `country_name` (`country_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## social_category
```sql
CREATE TABLE `social_category` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `social_category_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `category_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `category_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  PRIMARY KEY (`social_category_id`),
  UNIQUE KEY `category_code` (`category_code`),
  UNIQUE KEY `category_name` (`category_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## caste
```sql
CREATE TABLE `caste` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `caste_id` int unsigned NOT NULL AUTO_INCREMENT,
  `caste_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `caste_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `uncategorized_caste_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci GENERATED ALWAYS AS ((case when (`social_category_id` is null) then `caste_name` else NULL end)) STORED,
  `social_category_id` smallint unsigned DEFAULT NULL,
  PRIMARY KEY (`caste_id`),
  UNIQUE KEY `caste_code` (`caste_code`),
  UNIQUE KEY `uq_caste_name_category` (`social_category_id`,`caste_name`),
  UNIQUE KEY `uq_caste_uncategorized_name` (`uncategorized_caste_name`),
  CONSTRAINT `caste_social_category_id_378dd6e2_fk_social_ca` FOREIGN KEY (`social_category_id`) REFERENCES `social_category` (`social_category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## sub_caste
```sql
CREATE TABLE `sub_caste` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `sub_caste_id` int unsigned NOT NULL AUTO_INCREMENT,
  `sub_caste_code` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sub_caste_name` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `caste_id` int unsigned NOT NULL,
  PRIMARY KEY (`sub_caste_id`),
  UNIQUE KEY `uq_sub_caste` (`caste_id`,`sub_caste_name`),
  CONSTRAINT `sub_caste_caste_id_bc95f10f_fk_caste_caste_id` FOREIGN KEY (`caste_id`) REFERENCES `caste` (`caste_id`)
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

## institution
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
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## campus
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## department
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
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```
