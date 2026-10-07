# M8 dependency inspection

Read-only; no personal records inspected.

MySQL: 8.4.11

## M8 tables
- faculty_course_assignment: absent
- timetable_session: absent

## employee
```sql
CREATE TABLE `employee` (
  `employee_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `employee_number` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `agency_employee_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `first_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `middle_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `display_name` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `date_of_birth` date DEFAULT NULL,
  `primary_email` varchar(254) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `primary_phone` varchar(25) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `photo_url` varchar(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `joining_date` date NOT NULL,
  `employment_type` varchar(9) NOT NULL,
  `employment_status` varchar(10) NOT NULL DEFAULT 'DRAFT',
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `blood_group_id` tinyint unsigned DEFAULT NULL,
  `caste_id` int unsigned DEFAULT NULL,
  `gender_id` tinyint unsigned DEFAULT NULL,
  `institution_id` smallint unsigned NOT NULL,
  `nationality_country_id` smallint unsigned DEFAULT NULL,
  `religion_id` smallint unsigned DEFAULT NULL,
  `social_category_id` smallint unsigned DEFAULT NULL,
  `sub_caste_id` int unsigned DEFAULT NULL,
  `employment_source_id` tinyint unsigned NOT NULL,
  `external_agency_id` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`employee_id`),
  UNIQUE KEY `employee_number` (`employee_number`),
  UNIQUE KEY `uq_employee_agency_number` (`external_agency_id`,`agency_employee_number`),
  UNIQUE KEY `uq_employee_primary_email` (`primary_email`),
  KEY `m5_employee_scope` (`institution_id`,`employment_status`,`employee_number`),
  KEY `employee_blood_group_id_893f9c74_fk_blood_group_blood_group_id` (`blood_group_id`),
  KEY `employee_caste_id_dce194ef_fk_caste_caste_id` (`caste_id`),
  KEY `employee_gender_id_924d5520_fk_gender_gender_id` (`gender_id`),
  KEY `employee_nationality_country_id_7718a8ce_fk_country_country_id` (`nationality_country_id`),
  KEY `employee_religion_id_714d0c54_fk_religion_religion_id` (`religion_id`),
  KEY `employee_social_category_id_0a7ce52e_fk_social_ca` (`social_category_id`),
  KEY `employee_sub_caste_id_a445557d_fk_sub_caste_sub_caste_id` (`sub_caste_id`),
  KEY `employee_employment_source_id_170a3e53_fk_employmen` (`employment_source_id`),
  CONSTRAINT `employee_blood_group_id_893f9c74_fk_blood_group_blood_group_id` FOREIGN KEY (`blood_group_id`) REFERENCES `blood_group` (`blood_group_id`),
  CONSTRAINT `employee_caste_id_dce194ef_fk_caste_caste_id` FOREIGN KEY (`caste_id`) REFERENCES `caste` (`caste_id`),
  CONSTRAINT `employee_employment_source_id_170a3e53_fk_employmen` FOREIGN KEY (`employment_source_id`) REFERENCES `employment_source` (`employment_source_id`),
  CONSTRAINT `employee_external_agency_id_2d876e44_fk_external_` FOREIGN KEY (`external_agency_id`) REFERENCES `external_agency` (`external_agency_id`),
  CONSTRAINT `employee_gender_id_924d5520_fk_gender_gender_id` FOREIGN KEY (`gender_id`) REFERENCES `gender` (`gender_id`),
  CONSTRAINT `employee_institution_id_4e428a97_fk_institution_institution_id` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `employee_nationality_country_id_7718a8ce_fk_country_country_id` FOREIGN KEY (`nationality_country_id`) REFERENCES `country` (`country_id`),
  CONSTRAINT `employee_religion_id_714d0c54_fk_religion_religion_id` FOREIGN KEY (`religion_id`) REFERENCES `religion` (`religion_id`),
  CONSTRAINT `employee_social_category_id_0a7ce52e_fk_social_ca` FOREIGN KEY (`social_category_id`) REFERENCES `social_category` (`social_category_id`),
  CONSTRAINT `employee_sub_caste_id_a445557d_fk_sub_caste_sub_caste_id` FOREIGN KEY (`sub_caste_id`) REFERENCES `sub_caste` (`sub_caste_id`),
  CONSTRAINT `chk_m5_employee_employment_st` CHECK ((`employment_status` in (_utf8mb4'DRAFT',_utf8mb4'ACTIVE',_utf8mb4'ON_LEAVE',_utf8mb4'SUSPENDED',_utf8mb4'RESIGNED',_utf8mb4'RETIRED',_utf8mb4'TERMINATED'))),
  CONSTRAINT `chk_m5_employee_employment_ty` CHECK ((`employment_type` in (_utf8mb4'REGULAR',_utf8mb4'CONTRACT',_utf8mb4'VISITING',_utf8mb4'ADJUNCT',_utf8mb4'TEMPORARY',_utf8mb4'OTHER')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## employee_assignment
```sql
CREATE TABLE `employee_assignment` (
  `employee_assignment_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `is_primary` tinyint(1) NOT NULL DEFAULT '1',
  `current_primary_employee_id` bigint unsigned GENERATED ALWAYS AS ((case when ((`end_date` is null) and (`is_primary` = 1)) then `employee_id` else NULL end)) STORED,
  `campus_id` smallint unsigned NOT NULL,
  `department_id` smallint unsigned DEFAULT NULL,
  `designation_id` smallint unsigned NOT NULL,
  `employee_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`employee_assignment_id`),
  UNIQUE KEY `uq_employee_current_primary` (`current_primary_employee_id`),
  KEY `employee_assignment_campus_id_3f41f51e_fk_campus_campus_id` (`campus_id`),
  KEY `employee_assignment_designation_id_c4c0e5c7_fk_designati` (`designation_id`),
  KEY `employee_assignment_employee_id_fb90a337_fk_employee_employee_id` (`employee_id`),
  KEY `employee_assignment_department_id_8ddec955` (`department_id`),
  KEY `fk_employee_assignment_department_campus` (`department_id`,`campus_id`),
  CONSTRAINT `employee_assignment_campus_id_3f41f51e_fk_campus_campus_id` FOREIGN KEY (`campus_id`) REFERENCES `campus` (`campus_id`),
  CONSTRAINT `employee_assignment_designation_id_c4c0e5c7_fk_designati` FOREIGN KEY (`designation_id`) REFERENCES `designation` (`designation_id`),
  CONSTRAINT `employee_assignment_employee_id_fb90a337_fk_employee_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`),
  CONSTRAINT `fk_employee_assignment_department_campus` FOREIGN KEY (`department_id`, `campus_id`) REFERENCES `department` (`department_id`, `campus_id`),
  CONSTRAINT `chk_m5_employee_assignment_dates` CHECK (((`start_date` is null) or (`end_date` is null) or (`end_date` >= `start_date`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## employee_competency
```sql
CREATE TABLE `employee_competency` (
  `competency_level` varchar(12) DEFAULT NULL,
  `valid_from` date DEFAULT NULL,
  `valid_to` date DEFAULT NULL,
  `course_id` int unsigned NOT NULL,
  `employee_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`employee_id`,`course_id`),
  KEY `employee_competency_course_id_c7991e67_fk_course_ca` (`course_id`),
  CONSTRAINT `employee_competency_course_id_c7991e67_fk_course_ca` FOREIGN KEY (`course_id`) REFERENCES `course_catalog` (`course_id`),
  CONSTRAINT `employee_competency_employee_id_14722f90_fk_employee_employee_id` FOREIGN KEY (`employee_id`) REFERENCES `employee` (`employee_id`),
  CONSTRAINT `chk_m5_employee_competen_competency_le` CHECK ((`competency_level` in (_utf8mb4'BEGINNER',_utf8mb4'INTERMEDIATE',_utf8mb4'ADVANCED',_utf8mb4'EXPERT'))),
  CONSTRAINT `chk_m5_employee_competency_dates` CHECK (((`valid_from` is null) or (`valid_to` is null) or (`valid_to` >= `valid_from`)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## course_offering_section
```sql
CREATE TABLE `course_offering_section` (
  `version` bigint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `course_offering_section_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `class_batch_key` bigint unsigned GENERATED ALWAYS AS (coalesce(`class_batch_id`,0)) STORED,
  `session_type` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `class_batch_id` bigint unsigned DEFAULT NULL,
  `class_section_id` bigint unsigned NOT NULL,
  `course_offering_id` bigint unsigned NOT NULL,
  `created_by_id` bigint NOT NULL,
  `updated_by_id` bigint NOT NULL,
  `programme_term_offering_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`course_offering_section_id`),
  UNIQUE KEY `uq_course_offering_section_course` (`course_offering_section_id`,`course_offering_id`),
  UNIQUE KEY `uq_course_offering_section_owner` (`course_offering_section_id`,`programme_term_offering_id`),
  UNIQUE KEY `uq_m7_mapping_session` (`course_offering_section_id`,`session_type`),
  UNIQUE KEY `uq_course_offering_section` (`course_offering_id`,`class_section_id`,`class_batch_key`,`session_type`),
  KEY `course_offering_sect_created_by_id_ff169c24_fk_user_acco` (`created_by_id`),
  KEY `course_offering_sect_updated_by_id_ab6a866a_fk_user_acco` (`updated_by_id`),
  KEY `course_offering_sect_programme_term_offer_937d2465_fk_programme` (`programme_term_offering_id`),
  KEY `fk_course_offering_section_offering_owner` (`course_offering_id`,`programme_term_offering_id`),
  KEY `fk_course_offering_section_section_owner` (`class_section_id`,`programme_term_offering_id`),
  KEY `fk_course_offering_section_batch_owner` (`class_batch_id`,`class_section_id`),
  CONSTRAINT `course_offering_sect_class_batch_id_0609bd44_fk_class_bat` FOREIGN KEY (`class_batch_id`) REFERENCES `class_batch` (`class_batch_id`),
  CONSTRAINT `course_offering_sect_class_section_id_4c597fa3_fk_class_sec` FOREIGN KEY (`class_section_id`) REFERENCES `class_section` (`class_section_id`),
  CONSTRAINT `course_offering_sect_course_offering_id_20180d05_fk_course_of` FOREIGN KEY (`course_offering_id`) REFERENCES `course_offering` (`course_offering_id`),
  CONSTRAINT `course_offering_sect_created_by_id_ff169c24_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `course_offering_sect_programme_term_offer_937d2465_fk_programme` FOREIGN KEY (`programme_term_offering_id`) REFERENCES `programme_term_offering` (`programme_term_offering_id`),
  CONSTRAINT `course_offering_sect_updated_by_id_ab6a866a_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `fk_course_offering_section_batch_owner` FOREIGN KEY (`class_batch_id`, `class_section_id`) REFERENCES `class_batch` (`class_batch_id`, `class_section_id`),
  CONSTRAINT `fk_course_offering_section_offering_owner` FOREIGN KEY (`course_offering_id`, `programme_term_offering_id`) REFERENCES `course_offering` (`course_offering_id`, `programme_term_offering_id`),
  CONSTRAINT `fk_course_offering_section_section_owner` FOREIGN KEY (`class_section_id`, `programme_term_offering_id`) REFERENCES `class_section` (`class_section_id`, `programme_term_offering_id`),
  CONSTRAINT `chk_m7_mapping_session` CHECK ((`session_type` in (_utf8mb4'LECTURE',_utf8mb4'TUTORIAL',_utf8mb4'PRACTICAL',_utf8mb4'PROJECT',_utf8mb4'SEMINAR',_utf8mb4'OTHER'))),
  CONSTRAINT `course_offering_section_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## course_offering
```sql
CREATE TABLE `course_offering` (
  `version` bigint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `course_offering_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `offering_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `registration_capacity` smallint unsigned DEFAULT NULL,
  `status` varchar(9) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `course_id` int unsigned NOT NULL,
  `created_by_id` bigint NOT NULL,
  `curriculum_course_id` bigint unsigned DEFAULT NULL,
  `updated_by_id` bigint NOT NULL,
  `programme_term_offering_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`course_offering_id`),
  UNIQUE KEY `offering_code` (`offering_code`),
  UNIQUE KEY `uq_course_offering` (`programme_term_offering_id`,`course_id`),
  UNIQUE KEY `uq_course_offering_owner` (`course_offering_id`,`programme_term_offering_id`),
  KEY `course_offering_course_id_6a035476_fk_course_catalog_course_id` (`course_id`),
  KEY `course_offering_created_by_id_10ff92a4_fk_user_account_user_id` (`created_by_id`),
  KEY `course_offering_updated_by_id_86c269be_fk_user_account_user_id` (`updated_by_id`),
  KEY `fk_m7_curriculum_course_identity` (`curriculum_course_id`,`course_id`),
  CONSTRAINT `course_offering_course_id_6a035476_fk_course_catalog_course_id` FOREIGN KEY (`course_id`) REFERENCES `course_catalog` (`course_id`),
  CONSTRAINT `course_offering_created_by_id_10ff92a4_fk_user_account_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `course_offering_curriculum_course_id_88a13223_fk_curriculu` FOREIGN KEY (`curriculum_course_id`) REFERENCES `curriculum_course` (`curriculum_course_id`),
  CONSTRAINT `course_offering_programme_term_offer_7daaf3c3_fk_programme` FOREIGN KEY (`programme_term_offering_id`) REFERENCES `programme_term_offering` (`programme_term_offering_id`),
  CONSTRAINT `course_offering_updated_by_id_86c269be_fk_user_account_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `fk_m7_curriculum_course_identity` FOREIGN KEY (`curriculum_course_id`, `course_id`) REFERENCES `curriculum_course` (`curriculum_course_id`, `course_id`),
  CONSTRAINT `chk_m7_course_capacity` CHECK (((`registration_capacity` is null) or (`registration_capacity` > 0))),
  CONSTRAINT `chk_m7_course_status` CHECK ((`status` in (_utf8mb4'PLANNED',_utf8mb4'OPEN',_utf8mb4'ACTIVE',_utf8mb4'COMPLETED',_utf8mb4'CANCELLED'))),
  CONSTRAINT `course_offering_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `course_offering_chk_2` CHECK ((`registration_capacity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## programme_term_offering
```sql
CREATE TABLE `programme_term_offering` (
  `version` bigint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `programme_term_offering_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `specialization_key` smallint unsigned GENERATED ALWAYS AS (coalesce(`specialization_id`,0)) STORED,
  `status` varchar(17) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `academic_term_id` int unsigned NOT NULL,
  `created_by_id` bigint NOT NULL,
  `curriculum_scheme_id` int unsigned NOT NULL,
  `programme_id` smallint unsigned NOT NULL,
  `semester_id` tinyint unsigned NOT NULL,
  `specialization_id` smallint unsigned DEFAULT NULL,
  `updated_by_id` bigint NOT NULL,
  PRIMARY KEY (`programme_term_offering_id`),
  UNIQUE KEY `uq_m7_offering_programme` (`programme_term_offering_id`,`programme_id`),
  UNIQUE KEY `uq_programme_term` (`academic_term_id`,`programme_id`,`specialization_key`,`semester_id`),
  KEY `programme_term_offer_created_by_id_5444ac9f_fk_user_acco` (`created_by_id`),
  KEY `programme_term_offer_programme_id_60b21193_fk_programme` (`programme_id`),
  KEY `programme_term_offer_semester_id_b9ea9ca7_fk_semester_` (`semester_id`),
  KEY `programme_term_offer_updated_by_id_ba28119a_fk_user_acco` (`updated_by_id`),
  KEY `fk_m7_offering_scheme_programme` (`curriculum_scheme_id`,`programme_id`),
  KEY `fk_programme_term_specialization_programme` (`specialization_id`,`programme_id`),
  CONSTRAINT `fk_m7_offering_scheme_programme` FOREIGN KEY (`curriculum_scheme_id`, `programme_id`) REFERENCES `curriculum_scheme` (`curriculum_scheme_id`, `programme_id`),
  CONSTRAINT `fk_programme_term_specialization_programme` FOREIGN KEY (`specialization_id`, `programme_id`) REFERENCES `programme_specialization` (`specialization_id`, `programme_id`),
  CONSTRAINT `programme_term_offer_academic_term_id_c9fd87cd_fk_academic_` FOREIGN KEY (`academic_term_id`) REFERENCES `academic_term` (`academic_term_id`),
  CONSTRAINT `programme_term_offer_created_by_id_5444ac9f_fk_user_acco` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `programme_term_offer_curriculum_scheme_id_314d27d1_fk_curriculu` FOREIGN KEY (`curriculum_scheme_id`) REFERENCES `curriculum_scheme` (`curriculum_scheme_id`),
  CONSTRAINT `programme_term_offer_programme_id_60b21193_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`),
  CONSTRAINT `programme_term_offer_semester_id_b9ea9ca7_fk_semester_` FOREIGN KEY (`semester_id`) REFERENCES `semester` (`semester_id`),
  CONSTRAINT `programme_term_offer_specialization_id_5940af30_fk_programme` FOREIGN KEY (`specialization_id`) REFERENCES `programme_specialization` (`specialization_id`),
  CONSTRAINT `programme_term_offer_updated_by_id_ba28119a_fk_user_acco` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `chk_m7_offering_status` CHECK ((`status` in (_utf8mb4'PLANNED',_utf8mb4'REGISTRATION_OPEN',_utf8mb4'ACTIVE',_utf8mb4'COMPLETED',_utf8mb4'CANCELLED'))),
  CONSTRAINT `programme_term_offering_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## class_section
```sql
CREATE TABLE `class_section` (
  `version` bigint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `class_section_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `section_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `section_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `capacity` smallint unsigned DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_by_id` bigint NOT NULL,
  `home_room_id` int unsigned DEFAULT NULL,
  `updated_by_id` bigint NOT NULL,
  `programme_term_offering_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`class_section_id`),
  UNIQUE KEY `uq_class_section` (`programme_term_offering_id`,`section_code`),
  UNIQUE KEY `uq_class_section_owner` (`class_section_id`,`programme_term_offering_id`),
  KEY `class_section_created_by_id_fb9f7507_fk_user_account_user_id` (`created_by_id`),
  KEY `class_section_home_room_id_c1984bc4_fk_room_room_id` (`home_room_id`),
  KEY `class_section_updated_by_id_2b8092a9_fk_user_account_user_id` (`updated_by_id`),
  CONSTRAINT `class_section_created_by_id_fb9f7507_fk_user_account_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `class_section_home_room_id_c1984bc4_fk_room_room_id` FOREIGN KEY (`home_room_id`) REFERENCES `room` (`room_id`),
  CONSTRAINT `class_section_programme_term_offer_1c071ba0_fk_programme` FOREIGN KEY (`programme_term_offering_id`) REFERENCES `programme_term_offering` (`programme_term_offering_id`),
  CONSTRAINT `class_section_updated_by_id_2b8092a9_fk_user_account_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `chk_m7_section_capacity` CHECK (((`capacity` is null) or (`capacity` > 0))),
  CONSTRAINT `class_section_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `class_section_chk_2` CHECK ((`capacity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## class_batch
```sql
CREATE TABLE `class_batch` (
  `version` bigint unsigned NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `class_batch_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `batch_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `batch_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `capacity` smallint unsigned DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_by_id` bigint NOT NULL,
  `updated_by_id` bigint NOT NULL,
  `class_section_id` bigint unsigned NOT NULL,
  PRIMARY KEY (`class_batch_id`),
  UNIQUE KEY `uq_class_batch` (`class_section_id`,`batch_code`),
  UNIQUE KEY `uq_class_batch_owner` (`class_batch_id`,`class_section_id`),
  KEY `class_batch_created_by_id_f7594f36_fk_user_account_user_id` (`created_by_id`),
  KEY `class_batch_updated_by_id_7c8e843a_fk_user_account_user_id` (`updated_by_id`),
  CONSTRAINT `class_batch_class_section_id_e8e051f8_fk_class_sec` FOREIGN KEY (`class_section_id`) REFERENCES `class_section` (`class_section_id`),
  CONSTRAINT `class_batch_created_by_id_f7594f36_fk_user_account_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `class_batch_updated_by_id_7c8e843a_fk_user_account_user_id` FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`user_id`),
  CONSTRAINT `chk_m7_batch_capacity` CHECK (((`capacity` is null) or (`capacity` > 0))),
  CONSTRAINT `class_batch_chk_1` CHECK ((`version` >= 0)),
  CONSTRAINT `class_batch_chk_2` CHECK ((`capacity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
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

## time_slot
```sql
CREATE TABLE `time_slot` (
  `time_slot_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `slot_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_time` time(6) NOT NULL,
  `end_time` time(6) NOT NULL,
  `is_break` tinyint(1) NOT NULL DEFAULT '0',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `campus_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`time_slot_id`),
  UNIQUE KEY `uq_time_slot` (`campus_id`,`slot_code`),
  KEY `calendar_slot_available` (`campus_id`,`is_active`,`start_time`),
  CONSTRAINT `time_slot_campus_id_8f2f4728_fk_campus_campus_id` FOREIGN KEY (`campus_id`) REFERENCES `campus` (`campus_id`),
  CONSTRAINT `chk_time_slot` CHECK ((`end_time` > `start_time`))
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

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
