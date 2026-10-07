"""Frozen M12 baseline DDL and strict, non-destructive legacy adoption."""

import re

DDL = [
    "CREATE TABLE mentor_assignment (\n    mentor_assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    student_id BIGINT UNSIGNED NOT NULL,\n    employee_id BIGINT UNSIGNED NOT NULL,\n    start_date DATE NOT NULL,\n    end_date DATE NULL,\n    assignment_status ENUM('ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',\n    CONSTRAINT fk_mentor_assignment_student FOREIGN KEY (student_id) REFERENCES student(student_id),\n    CONSTRAINT fk_mentor_assignment_employee FOREIGN KEY (employee_id) REFERENCES employee(employee_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE counselling_session (\n    counselling_session_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    mentor_assignment_id BIGINT UNSIGNED NOT NULL,\n    session_date DATETIME NOT NULL,\n    observations TEXT NULL,\n    action_plan TEXT NULL,\n    follow_up_date DATE NULL,\n    session_status ENUM('SCHEDULED','COMPLETED','CANCELLED','FOLLOW_UP_REQUIRED') NOT NULL DEFAULT 'COMPLETED',\n    confidentiality_level ENUM('NORMAL','RESTRICTED','HIGHLY_RESTRICTED') NOT NULL DEFAULT 'RESTRICTED',\n    CONSTRAINT fk_counselling_mentor_assignment FOREIGN KEY (mentor_assignment_id) REFERENCES mentor_assignment(mentor_assignment_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE grievance_category (\n    grievance_category_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    category_code VARCHAR(30) NOT NULL UNIQUE,\n    category_name VARCHAR(100) NOT NULL UNIQUE,\n    is_active BOOLEAN NOT NULL DEFAULT TRUE\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE grievance (\n    grievance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    grievance_number VARCHAR(30) NOT NULL UNIQUE,\n    student_id BIGINT UNSIGNED NOT NULL,\n    grievance_category_id SMALLINT UNSIGNED NOT NULL,\n    department_id SMALLINT UNSIGNED NULL,\n    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n    subject VARCHAR(200) NOT NULL,\n    description TEXT NOT NULL,\n    priority ENUM('LOW','NORMAL','HIGH','URGENT') NOT NULL DEFAULT 'NORMAL',\n    status ENUM('SUBMITTED','ASSIGNED','UNDER_REVIEW','RESOLVED','REJECTED','CLOSED') NOT NULL DEFAULT 'SUBMITTED',\n    resolved_at DATETIME NULL,\n    resolution TEXT NULL,\n    CONSTRAINT fk_grievance_student FOREIGN KEY (student_id) REFERENCES student(student_id),\n    CONSTRAINT fk_grievance_category FOREIGN KEY (grievance_category_id) REFERENCES grievance_category(grievance_category_id),\n    CONSTRAINT fk_grievance_department FOREIGN KEY (department_id) REFERENCES department(department_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE grievance_action (\n    grievance_action_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    grievance_id BIGINT UNSIGNED NOT NULL,\n    action_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n    action_type VARCHAR(50) NOT NULL,\n    action_notes TEXT NULL,\n    new_status VARCHAR(30) NULL,\n    CONSTRAINT fk_grievance_action_grievance FOREIGN KEY (grievance_id) REFERENCES grievance(grievance_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
]


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
        raise RuntimeError("M12 incompatible table engine/collation: " + table)
    expected = {}
    for line in sql.splitlines()[1:]:
        line = line.strip().rstrip(",")
        if not line or line.startswith(("CONSTRAINT", ")")):
            continue
        match = re.match(
            r"(\w+)\s+(ENUM\([^)]*\)|VARCHAR\(\d+\)|BIGINT UNSIGNED|SMALLINT UNSIGNED|DATETIME|DATE|TEXT|BOOLEAN)(.*)",
            line,
            re.IGNORECASE,
        )
        if not match:
            raise RuntimeError("Unrecognized canonical DDL")
        name, kind, tail = match.groups()
        kind = (
            ("enum" + kind[4:])
            if kind.startswith("ENUM")
            else kind.lower().replace("boolean", "tinyint(1)")
        )
        default = re.search(r"DEFAULT (CURRENT_TIMESTAMP|TRUE|FALSE|'[^']*')", tail)
        value = default[1].strip("'") if default else None
        value = {
            "CURRENT_TIMESTAMP": "current_timestamp()",
            "TRUE": "1",
            "FALSE": "0",
        }.get(value, value)
        expected[name] = (
            kind,
            "NO" if "NOT NULL" in tail or "PRIMARY KEY" in tail else "YES",
            value,
            "auto_increment" if "AUTO_INCREMENT" in tail else "",
        )
    cursor.execute(
        "SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLUMN_DEFAULT,EXTRA FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        [table],
    )
    actual = {
        name: (
            kind,
            nullable,
            "current_timestamp()"
            if str(default).lower() in ("current_timestamp", "current_timestamp()")
            else default,
            "auto_increment" if "auto_increment" in extra else "",
        )
        for name, kind, nullable, default, extra in cursor.fetchall()
    }
    if actual != expected:
        raise RuntimeError("M12 incompatible columns/defaults: " + table)
    cursor.execute(
        "SELECT COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND REFERENCED_TABLE_NAME IS NOT NULL",
        [table],
    )
    expected_fk = set(
        re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", sql)
    )
    if set(cursor.fetchall()) != expected_fk:
        raise RuntimeError("M12 incompatible foreign keys: " + table)
    cursor.execute(
        "SELECT COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND NON_UNIQUE=0 AND INDEX_NAME<>'PRIMARY'",
        [table],
    )
    expected_unique = {
        name for name in expected if re.search(r"\b" + name + r"\s+[^\n]*\bUNIQUE", sql)
    }
    if {row[0] for row in cursor.fetchall()} != expected_unique:
        raise RuntimeError("M12 incompatible unique keys: " + table)
    cursor.execute(
        "SELECT DELETE_RULE,UPDATE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        [table],
    )
    if any(
        d not in ("RESTRICT", "NO ACTION") or u not in ("RESTRICT", "NO ACTION")
        for d, u in cursor.fetchall()
    ):
        raise RuntimeError("M12 unsafe cascading foreign key: " + table)
    cursor.execute(
        "SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SEQ_IN_INDEX FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX",
        [table],
    )
    indexes = {}
    for name, non_unique, column, position in cursor.fetchall():
        indexes.setdefault((name, non_unique), []).append(column)
    primary = next(
        name
        for name in expected
        if re.search(r"\b" + name + r"\s+[^\n]*PRIMARY KEY", sql)
    )
    signatures = {
        (non_unique, tuple(columns)) for (name, non_unique), columns in indexes.items()
    }
    wanted = (
        {(0, (primary,))}
        | {(0, (name,)) for name in expected_unique}
        | {(1, (name,)) for name, _, _ in expected_fk}
    )
    if signatures != wanted or indexes.get(("PRIMARY", 0)) != [primary]:
        raise RuntimeError("M12 incompatible indexes: " + table)
    cursor.execute(
        "SELECT COLUMN_NAME,COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLLATION_NAME IS NOT NULL",
        [table],
    )
    if any(collation != "utf8mb4_unicode_ci" for _, collation in cursor.fetchall()):
        raise RuntimeError("M12 incompatible column collation: " + table)
    return True


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        raise RuntimeError("M12 canonical schema requires MySQL.")
    with schema_editor.connection.cursor() as cursor:
        # Validate all existing tables before creating any missing table.
        present = [verify(cursor, sql) for sql in DDL]
        for exists, sql in zip(present, DDL):
            if not exists:
                cursor.execute(sql)
        for sql in DDL:
            verify(cursor, sql)


# Reverse intentionally retains domain tables and data. Reapply verifies/adopts them.
def retain(apps, schema_editor):
    pass
