"""Frozen canonical M13 DDL; verify before adopting legacy tables."""

import re

DDL = [
    "CREATE TABLE file_object (\n    file_object_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    storage_provider VARCHAR(30) NOT NULL,\n    storage_key VARCHAR(500) NOT NULL UNIQUE,\n    original_file_name VARCHAR(255) NOT NULL,\n    mime_type VARCHAR(100) NOT NULL,\n    file_size_bytes BIGINT UNSIGNED NOT NULL,\n    checksum_sha256 CHAR(64) NULL,\n    stored_file_name VARCHAR(255) NULL,\n    storage_url VARCHAR(1000) NULL,\n    file_extension VARCHAR(20) NULL,\n    confidentiality_level ENUM('PUBLIC','INTERNAL','CONFIDENTIAL','RESTRICTED','HIGHLY_RESTRICTED') NOT NULL DEFAULT 'INTERNAL',\n    is_encrypted BOOLEAN NOT NULL DEFAULT FALSE,\n    uploaded_by_user_id BIGINT UNSIGNED NULL,\n    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,\n    deleted_at TIMESTAMP NULL,\n    CONSTRAINT chk_file_object_size CHECK (file_size_bytes > 0),\n    CONSTRAINT chk_file_object_checksum CHECK (checksum_sha256 IS NULL OR checksum_sha256 REGEXP '^[0-9A-Fa-f]{64}$')\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE student_document (\n    student_document_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    student_id BIGINT UNSIGNED NOT NULL,\n    document_type_id SMALLINT UNSIGNED NOT NULL,\n    file_object_id BIGINT UNSIGNED NOT NULL,\n    document_number VARCHAR(100) NULL,\n    issue_date DATE NULL,\n    expiry_date DATE NULL,\n    verification_status ENUM('PENDING','VERIFIED','REJECTED','EXPIRED') NOT NULL DEFAULT 'PENDING',\n    verified_at DATETIME NULL,\n    remarks VARCHAR(500) NULL,\n    CONSTRAINT uq_student_document UNIQUE (student_id, document_type_id, document_number),\n    CONSTRAINT fk_student_document_student FOREIGN KEY (student_id) REFERENCES student(student_id),\n    CONSTRAINT fk_student_document_type FOREIGN KEY (document_type_id) REFERENCES document_type(document_type_id),\n    CONSTRAINT fk_student_document_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE certificate_type (\n    certificate_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    certificate_code VARCHAR(30) NOT NULL UNIQUE,\n    certificate_name VARCHAR(100) NOT NULL UNIQUE,\n    is_active BOOLEAN NOT NULL DEFAULT TRUE\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE certificate_request (\n    certificate_request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    request_number VARCHAR(30) NOT NULL UNIQUE,\n    student_id BIGINT UNSIGNED NOT NULL,\n    certificate_type_id SMALLINT UNSIGNED NOT NULL,\n    requested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n    purpose VARCHAR(500) NULL,\n    request_status ENUM('SUBMITTED','UNDER_REVIEW','APPROVED','REJECTED','ISSUED','CANCELLED') NOT NULL DEFAULT 'SUBMITTED',\n    issued_at DATETIME NULL,\n    certificate_number VARCHAR(50) NULL UNIQUE,\n    file_object_id BIGINT UNSIGNED NULL,\n    CONSTRAINT fk_certificate_request_student FOREIGN KEY (student_id) REFERENCES student(student_id),\n    CONSTRAINT fk_certificate_request_type FOREIGN KEY (certificate_type_id) REFERENCES certificate_type(certificate_type_id),\n    CONSTRAINT fk_certificate_request_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE student_exit (\n    student_exit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    enrolment_id BIGINT UNSIGNED NOT NULL,\n    exit_type ENUM('COMPLETION','TRANSFER','WITHDRAWAL','TERMINATION','OTHER') NOT NULL,\n    exit_date DATE NOT NULL,\n    destination_institution VARCHAR(250) NULL,\n    old_registration_number VARCHAR(50) NULL,\n    remarks TEXT NULL,\n    CONSTRAINT uq_student_exit_enrolment UNIQUE (enrolment_id),\n    CONSTRAINT fk_student_exit_enrolment FOREIGN KEY (enrolment_id) REFERENCES student_programme_enrolment(enrolment_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
]


def signature(cursor, table):
    cursor.execute(
        "SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
        [table],
    )
    return list(cursor.fetchall())


def verify(cursor, sql):
    table = re.search(r"CREATE TABLE (\w+)", sql)[1]
    cursor.execute(
        "SELECT ENGINE,TABLE_COLLATION FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        [table],
    )
    row = cursor.fetchone()
    if not row:
        return False
    if tuple(str(v).lower() for v in row) != ("innodb", "utf8mb4_unicode_ci"):
        raise RuntimeError("M13 incompatible engine/collation: " + table)
    # M15 retains signed user IDs and adds the uploader FK. Recognize only that
    # explicitly recorded upgrade; the frozen pre-M15 DDL remains unchanged.
    if table == "file_object":
        cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app='documents_exit' AND name='0003_m15_uploader_identity'")
        if cursor.fetchone()[0]:
            sql = sql.replace("uploaded_by_user_id BIGINT UNSIGNED NULL", "uploaded_by_user_id BIGINT NULL")
            sql = sql.replace("\n) ENGINE", ",\n    CONSTRAINT fk_file_object_uploaded_by FOREIGN KEY (uploaded_by_user_id) REFERENCES user_account(user_id)\n) ENGINE")
    expected = {}
    unique = set()
    primary = None
    for line in sql.splitlines()[1:]:
        line = line.strip().rstrip(",")
        if not line or line.startswith(("CONSTRAINT", ")")):
            continue
        match = re.match(
            r"(\w+)\s+(ENUM\([^)]*\)|VARCHAR\(\d+\)|CHAR\(\d+\)|BIGINT UNSIGNED|BIGINT|SMALLINT UNSIGNED|DATETIME|TIMESTAMP|DATE|TEXT|BOOLEAN)(.*)",
            line,
            re.IGNORECASE,
        )
        if not match:
            raise RuntimeError("Unrecognized DDL")
        name, kind, tail = match.groups()
        kind = (
            ("enum" + kind[4:])
            if kind.startswith("ENUM")
            else kind.lower().replace("boolean", "tinyint(1)")
        )
        default = re.search(r"DEFAULT (CURRENT_TIMESTAMP|TRUE|FALSE|'[^']*')", tail)
        value = default[1].strip("'") if default else None
        value = {
            "CURRENT_TIMESTAMP": "current_timestamp",
            "TRUE": "1",
            "FALSE": "0",
        }.get(value, value)
        expected[name] = (
            kind,
            "NO" if "NOT NULL" in tail or "PRIMARY KEY" in tail else "YES",
            value,
            "AUTO_INCREMENT" in tail,
            "ON UPDATE CURRENT_TIMESTAMP" in tail,
        )
        if "PRIMARY KEY" in tail:
            primary = name
        if "UNIQUE" in tail:
            unique.add((name,))
    actual = {}
    for name, kind, nullable, default, extra, collation in signature(cursor, table):
        if collation and collation != "utf8mb4_unicode_ci":
            raise RuntimeError("M13 incompatible column collation: " + table)
        default = (
            "current_timestamp"
            if str(default).lower() in ["current_timestamp", "current_timestamp()"]
            else default
        )
        actual[name] = (
            kind,
            nullable,
            default,
            "auto_increment" in extra.lower(),
            "on update current_timestamp" in extra.lower(),
        )
    if actual != expected:
        raise RuntimeError("M13 incompatible columns/defaults: " + table)
    unique |= {
        tuple(x.strip() for x in cols.split(","))
        for cols in re.findall(r"CONSTRAINT \w+ UNIQUE \(([^)]+)\)", sql)
    }
    fk = set(re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", sql))
    cursor.execute(
        "SELECT COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",
        [table],
    )
    if set(cursor.fetchall()) != fk:
        raise RuntimeError("M13 incompatible foreign keys: " + table)
    cursor.execute(
        "SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX",
        [table],
    )
    indexes = {}
    for name, non_unique, column, prefix in cursor.fetchall():
        if prefix is not None:
            raise RuntimeError(
                "M13 prefix indexes do not match canonical uniqueness: " + table
            )
        indexes.setdefault((name, non_unique), []).append(column)
    wanted = {(0, (primary,))} | {(0, columns) for columns in unique}
    for column, _, _ in fk:
        if not any(cols[0] == column for _, cols in wanted):
            wanted.add((1, (column,)))
    if {(n, tuple(cols)) for (_, n), cols in indexes.items()} != wanted or indexes.get(
        ("PRIMARY", 0)
    ) != [primary]:
        raise RuntimeError("M13 incompatible indexes: " + table)
    cursor.execute(
        "SELECT DELETE_RULE,UPDATE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        [table],
    )
    if any(
        d not in ("RESTRICT", "NO ACTION") or u not in ("RESTRICT", "NO ACTION")
        for d, u in cursor.fetchall()
    ):
        raise RuntimeError("M13 unsafe foreign key actions: " + table)
    cursor.execute(
        "SELECT CONSTRAINT_NAME,CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND CONSTRAINT_NAME IN (SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND CONSTRAINT_TYPE='CHECK')",
        [table],
    )
    checks = dict(cursor.fetchall())
    expected_checks = dict(re.findall(r"CONSTRAINT (\w+) CHECK \((.*)\)", sql))

    def normalize(value):
        value = re.sub(
            r"(checksum_sha256) REGEXP ('[^']*')",
            r"regexp_like(\1,\2)",
            value,
            flags=re.IGNORECASE,
        )
        return re.sub(
            r"[\s`()]+",
            "",
            value.replace("_utf8mb4", "").replace(chr(92) + chr(39), chr(39)),
        ).lower()

    if {k: normalize(v) for k, v in checks.items()} != {
        k: normalize(v) for k, v in expected_checks.items()
    }:
        raise RuntimeError("M13 incompatible checks: " + table)
    return True


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        raise RuntimeError("M13 requires MySQL canonical schema.")
    with schema_editor.connection.cursor() as cursor:
        present = [verify(cursor, sql) for sql in DDL]
        for exists, sql in zip(present, DDL):
            if not exists:
                cursor.execute(sql)
        for sql in DDL:
            verify(cursor, sql)


def retain(apps, schema_editor):
    pass
