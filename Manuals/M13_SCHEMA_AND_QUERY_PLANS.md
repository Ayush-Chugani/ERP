# M13 canonical schema and local query plans

Verified against the supplied DDL; native TIMESTAMP/ENUM/check/unique/FK semantics are preserved.

## file_object

```sql

CREATE TABLE `file_object` (
  `file_object_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `storage_provider` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `storage_key` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_file_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `mime_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_size_bytes` bigint unsigned NOT NULL,
  `checksum_sha256` char(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `stored_file_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `storage_url` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_extension` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `confidentiality_level` enum('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED','HIGHLY_RESTRICTED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'INTERNAL',
  `is_encrypted` tinyint(1) NOT NULL DEFAULT '0',
  `uploaded_by_user_id` bigint unsigned DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`file_object_id`),
  UNIQUE KEY `storage_key` (`storage_key`),
  CONSTRAINT `chk_file_object_checksum` CHECK (((`checksum_sha256` is null) or regexp_like(`checksum_sha256`,_utf8mb4'^[0-9A-Fa-f]{64}$'))),
  CONSTRAINT `chk_file_object_size` CHECK ((`file_size_bytes` > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## student_document

```sql

CREATE TABLE `student_document` (
  `student_document_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `student_id` bigint unsigned NOT NULL,
  `document_type_id` smallint unsigned NOT NULL,
  `file_object_id` bigint unsigned NOT NULL,
  `document_number` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `issue_date` date DEFAULT NULL,
  `expiry_date` date DEFAULT NULL,
  `verification_status` enum('PENDING','VERIFIED','REJECTED','EXPIRED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'PENDING',
  `verified_at` datetime DEFAULT NULL,
  `remarks` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`student_document_id`),
  UNIQUE KEY `uq_student_document` (`student_id`,`document_type_id`,`document_number`),
  KEY `fk_student_document_type` (`document_type_id`),
  KEY `fk_student_document_file` (`file_object_id`),
  CONSTRAINT `fk_student_document_file` FOREIGN KEY (`file_object_id`) REFERENCES `file_object` (`file_object_id`),
  CONSTRAINT `fk_student_document_student` FOREIGN KEY (`student_id`) REFERENCES `student` (`student_id`),
  CONSTRAINT `fk_student_document_type` FOREIGN KEY (`document_type_id`) REFERENCES `document_type` (`document_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## certificate_type

```sql

CREATE TABLE `certificate_type` (
  `certificate_type_id` smallint unsigned NOT NULL AUTO_INCREMENT,
  `certificate_code` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `certificate_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`certificate_type_id`),
  UNIQUE KEY `certificate_code` (`certificate_code`),
  UNIQUE KEY `certificate_name` (`certificate_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## certificate_request

```sql

CREATE TABLE `certificate_request` (
  `certificate_request_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `request_number` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `student_id` bigint unsigned NOT NULL,
  `certificate_type_id` smallint unsigned NOT NULL,
  `requested_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `purpose` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `request_status` enum('SUBMITTED','UNDER_REVIEW','APPROVED','REJECTED','ISSUED','CANCELLED') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'SUBMITTED',
  `issued_at` datetime DEFAULT NULL,
  `certificate_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_object_id` bigint unsigned DEFAULT NULL,
  PRIMARY KEY (`certificate_request_id`),
  UNIQUE KEY `request_number` (`request_number`),
  UNIQUE KEY `certificate_number` (`certificate_number`),
  KEY `fk_certificate_request_student` (`student_id`),
  KEY `fk_certificate_request_type` (`certificate_type_id`),
  KEY `fk_certificate_request_file` (`file_object_id`),
  CONSTRAINT `fk_certificate_request_file` FOREIGN KEY (`file_object_id`) REFERENCES `file_object` (`file_object_id`),
  CONSTRAINT `fk_certificate_request_student` FOREIGN KEY (`student_id`) REFERENCES `student` (`student_id`),
  CONSTRAINT `fk_certificate_request_type` FOREIGN KEY (`certificate_type_id`) REFERENCES `certificate_type` (`certificate_type_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

## student_exit

```sql

CREATE TABLE `student_exit` (
  `student_exit_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `enrolment_id` bigint unsigned NOT NULL,
  `exit_type` enum('COMPLETION','TRANSFER','WITHDRAWAL','TERMINATION','OTHER') COLLATE utf8mb4_unicode_ci NOT NULL,
  `exit_date` date NOT NULL,
  `destination_institution` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `old_registration_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `remarks` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`student_exit_id`),
  UNIQUE KEY `uq_student_exit_enrolment` (`enrolment_id`),
  CONSTRAINT `fk_student_exit_enrolment` FOREIGN KEY (`enrolment_id`) REFERENCES `student_programme_enrolment` (`enrolment_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci

```

```sql

SELECT student_document_id,verification_status FROM student_document WHERE student_id=1

```

```

((1, 'SIMPLE', 'student_document', None, 'ref', 'uq_student_document', 'uq_student_document', '8', 'const', 1, 100.0, None),)

```

```sql

SELECT certificate_request_id,request_status FROM certificate_request WHERE student_id=1 AND request_status='APPROVED'

```

```

((1, 'SIMPLE', 'certificate_request', None, 'ref', 'fk_certificate_request_student', 'fk_certificate_request_student', '8', 'const', 1, 100.0, 'Using where'),)

```

```sql

SELECT * FROM student_exit WHERE enrolment_id=1

```

```

((1, 'SIMPLE', None, None, None, None, None, None, None, None, None, 'no matching row in const table'),)

```

Plans describe the local development database only; populated load and storage throughput require separate acceptance.