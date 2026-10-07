import re

DDL = [
    "CREATE TABLE announcement_type (\n    announcement_type_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    type_code VARCHAR(30) NOT NULL UNIQUE,\n    type_name VARCHAR(100) NOT NULL UNIQUE,\n    is_active BOOLEAN NOT NULL DEFAULT TRUE\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE announcement (\n    announcement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,\n    announcement_type_id SMALLINT UNSIGNED NOT NULL,\n    department_id SMALLINT UNSIGNED NULL,\n    title VARCHAR(250) NOT NULL,\n    description TEXT NOT NULL,\n    publish_from DATETIME NOT NULL,\n    publish_to DATETIME NULL,\n    approval_status ENUM('DRAFT','PENDING','APPROVED','REJECTED','ARCHIVED') NOT NULL DEFAULT 'DRAFT',\n    audience_type ENUM('ALL','STUDENTS','STAFF','PROGRAMME','DEPARTMENT','CUSTOM') NOT NULL DEFAULT 'ALL',\n    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,\n    CONSTRAINT fk_announcement_type FOREIGN KEY (announcement_type_id) REFERENCES announcement_type(announcement_type_id),\n    CONSTRAINT fk_announcement_department FOREIGN KEY (department_id) REFERENCES department(department_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
    "CREATE TABLE announcement_attachment (\n    announcement_id BIGINT UNSIGNED NOT NULL,\n    file_object_id BIGINT UNSIGNED NOT NULL,\n    display_order SMALLINT UNSIGNED NULL,\n    PRIMARY KEY (announcement_id, file_object_id),\n    CONSTRAINT fk_announcement_attachment_announcement FOREIGN KEY (announcement_id) REFERENCES announcement(announcement_id),\n    CONSTRAINT fk_announcement_attachment_file FOREIGN KEY (file_object_id) REFERENCES file_object(file_object_id)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;",
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
        raise RuntimeError("M14 incompatible engine/collation: " + table)
    expected = {}
    unique = set()
    primary = None
    for line in sql.splitlines()[1:]:
        line = line.strip().rstrip(",")
        if not line or line.startswith(("CONSTRAINT", "PRIMARY KEY", ")")):
            continue
        match = re.match(
            r"(\w+)\s+(ENUM\([^)]*\)|VARCHAR\(\d+\)|CHAR\(\d+\)|BIGINT UNSIGNED|SMALLINT UNSIGNED|DATETIME|TIMESTAMP|DATE|TEXT|BOOLEAN)(.*)",
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
            primary = (name,)
        if "UNIQUE" in tail:
            unique.add((name,))
    composite = re.search(r"PRIMARY KEY \(([^)]+)\)", sql)
    if composite:
        primary = tuple(x.strip() for x in composite[1].split(","))
    actual = {}
    for name, kind, nullable, default, extra, collation in signature(cursor, table):
        if collation and collation != "utf8mb4_unicode_ci":
            raise RuntimeError("M14 incompatible column collation: " + table)
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
        raise RuntimeError("M14 incompatible columns/defaults: " + table)
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
        raise RuntimeError("M14 incompatible foreign keys: " + table)
    cursor.execute(
        "SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX",
        [table],
    )
    indexes = {}
    for name, non_unique, column, prefix in cursor.fetchall():
        if prefix is not None:
            raise RuntimeError(
                "M14 prefix indexes do not match canonical uniqueness: " + table
            )
        indexes.setdefault((name, non_unique), []).append(column)
    wanted = {(0, primary)} | {(0, columns) for columns in unique}
    for column, _, _ in fk:
        if not any(cols[0] == column for _, cols in wanted):
            wanted.add((1, (column,)))
    if {(n, tuple(cols)) for (_, n), cols in indexes.items()} != wanted or indexes.get(
        ("PRIMARY", 0)
    ) != list(primary):
        raise RuntimeError("M14 incompatible indexes: " + table)
    cursor.execute(
        "SELECT DELETE_RULE,UPDATE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        [table],
    )
    if any(
        d not in ("RESTRICT", "NO ACTION") or u not in ("RESTRICT", "NO ACTION")
        for d, u in cursor.fetchall()
    ):
        raise RuntimeError("M14 unsafe foreign key actions: " + table)
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
        raise RuntimeError("M14 incompatible checks: " + table)
    return True


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        raise RuntimeError("M14 requires MySQL canonical schema.")
    with schema_editor.connection.cursor() as cursor:
        present = [verify(cursor, sql) for sql in DDL]
        for exists, sql in zip(present, DDL):
            if not exists:
                cursor.execute(sql)
        for sql in DDL:
            verify(cursor, sql)


def retain(apps, schema_editor):
    pass
