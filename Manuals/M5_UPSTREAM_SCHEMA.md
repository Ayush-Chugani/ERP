# M5 live schema preflight

Read-only inspection; no personal records or credentials are collected.

Database version: 8.4.11

## Target tables

- student: absent
- student_address: absent
- student_parent_guardian: absent
- student_residence: absent
- student_previous_education: absent
- student_entrance_exam: absent
- staff_type: absent
- staff_category: absent
- employment_source: absent
- external_agency: absent
- designation: absent
- employee: absent
- employee_address: absent
- employee_assignment: absent
- employee_competency: absent

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

## state
```sql
CREATE TABLE `state` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `state_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `state_code` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `state_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `country_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`state_id`),
  UNIQUE KEY `uq_state_country_code` (`country_id`,`state_code`),
  UNIQUE KEY `uq_state_country_name` (`country_id`,`state_name`),
  CONSTRAINT `state_country_id_6b36f831_fk_country_country_id` FOREIGN KEY (`country_id`) REFERENCES `country` (`country_id`)
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

## blood_group
```sql
CREATE TABLE `blood_group` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `blood_group_id` tinyint unsigned NOT NULL AUTO_INCREMENT,
  `blood_group_code` varchar(5) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  PRIMARY KEY (`blood_group_id`),
  UNIQUE KEY `blood_group_code` (`blood_group_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

## religion
```sql
CREATE TABLE `religion` (
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `religion_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `religion_code` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `religion_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  PRIMARY KEY (`religion_id`),
  UNIQUE KEY `religion_name` (`religion_name`),
  UNIQUE KEY `religion_code` (`religion_code`)
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
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
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
