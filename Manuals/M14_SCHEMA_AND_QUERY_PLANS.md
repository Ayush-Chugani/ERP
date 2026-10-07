# M14 schema and local query plans

Baseline tables plus explicitly approved institution ownership and programme/user targets. These local empty-table plans do not establish production performance.

## announcement_type

```sql

CREATE TABLE `announcement_type` (
  `announcement_type_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `type_code` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`announcement_type_id`),
  UNIQUE KEY `type_code` (`type_code`),
  UNIQUE KEY `type_name` (`type_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## announcement

```sql

CREATE TABLE `announcement` (
  `announcement_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `announcement_type_id` smallint unsigned NOT NULL,
  `department_id` smallint unsigned DEFAULT NULL,
  `title` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `publish_from` datetime NOT NULL,
  `publish_to` datetime DEFAULT NULL,
  `approval_status` enum('DRAFT','PENDING','APPROVED','REJECTED','ARCHIVED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'DRAFT',
  `audience_type` enum('ALL','STUDENTS','STAFF','PROGRAMME','DEPARTMENT','CUSTOM') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ALL',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `institution_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`announcement_id`),
  KEY `fk_announcement_type` (`announcement_type_id`),
  KEY `fk_announcement_department` (`department_id`),
  KEY `announcement_institution_id_25099035_fk_instituti` (`institution_id`),
  CONSTRAINT `announcement_institution_id_25099035_fk_instituti` FOREIGN KEY (`institution_id`) REFERENCES `institution` (`institution_id`),
  CONSTRAINT `fk_announcement_department` FOREIGN KEY (`department_id`) REFERENCES `department` (`department_id`),
  CONSTRAINT `fk_announcement_type` FOREIGN KEY (`announcement_type_id`) REFERENCES `announcement_type` (`announcement_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## announcement_attachment

```sql

CREATE TABLE `announcement_attachment` (
  `announcement_id` bigint unsigned NOT NULL,
  `file_object_id` bigint unsigned NOT NULL,
  `display_order` smallint unsigned DEFAULT NULL,
  PRIMARY KEY (`announcement_id`,`file_object_id`),
  KEY `fk_announcement_attachment_file` (`file_object_id`),
  CONSTRAINT `fk_announcement_attachment_announcement` FOREIGN KEY (`announcement_id`) REFERENCES `announcement` (`announcement_id`),
  CONSTRAINT `fk_announcement_attachment_file` FOREIGN KEY (`file_object_id`) REFERENCES `file_object` (`file_object_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## announcement_programme_target

```sql

CREATE TABLE `announcement_programme_target` (
  `announcement_id` bigint unsigned NOT NULL,
  `programme_id` smallint unsigned NOT NULL,
  PRIMARY KEY (`announcement_id`,`programme_id`),
  KEY `announcement_program_programme_id_d7b9cc3f_fk_programme` (`programme_id`),
  CONSTRAINT `announcement_program_announcement_id_5744f46b_fk_announcem` FOREIGN KEY (`announcement_id`) REFERENCES `announcement` (`announcement_id`),
  CONSTRAINT `announcement_program_programme_id_d7b9cc3f_fk_programme` FOREIGN KEY (`programme_id`) REFERENCES `programme` (`programme_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## announcement_user_target

```sql

CREATE TABLE `announcement_user_target` (
  `announcement_id` bigint unsigned NOT NULL,
  `user_id` bigint NOT NULL,
  PRIMARY KEY (`announcement_id`,`user_id`),
  KEY `announcement_user_ta_user_id_d13870e1_fk_user_acco` (`user_id`),
  CONSTRAINT `announcement_user_ta_announcement_id_2705f917_fk_announcem` FOREIGN KEY (`announcement_id`) REFERENCES `announcement` (`announcement_id`),
  CONSTRAINT `announcement_user_ta_user_id_d13870e1_fk_user_acco` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

```sql

SELECT announcement_id FROM announcement WHERE institution_id=1 AND approval_status='APPROVED' AND publish_from<=UTC_TIMESTAMP() AND (publish_to IS NULL OR publish_to>UTC_TIMESTAMP()) ORDER BY publish_from DESC,announcement_id DESC LIMIT 50

```

```

((1, 'SIMPLE', 'announcement', None, 'ref', 'announcement_institution_id_25099035_fk_instituti', 'announcement_institution_id_25099035_fk_instituti', '2', 'const', 1, 100.0, 'Using where; Using filesort'),)

```

```sql

SELECT * FROM announcement_programme_target WHERE programme_id=1

```

```

((1, 'SIMPLE', 'announcement_programme_target', None, 'ref', 'PRIMARY,announcement_program_programme_id_d7b9cc3f_fk_programme', 'announcement_program_programme_id_d7b9cc3f_fk_programme', '2', 'const', 1, 100.0, 'Using index'),)

```

```sql

SELECT * FROM announcement_user_target WHERE user_id=1

```

```

((1, 'SIMPLE', 'announcement_user_target', None, 'ref', 'PRIMARY,announcement_user_ta_user_id_d13870e1_fk_user_acco', 'announcement_user_ta_user_id_d13870e1_fk_user_acco', '8', 'const', 1, 100.0, 'Using index'),)

```