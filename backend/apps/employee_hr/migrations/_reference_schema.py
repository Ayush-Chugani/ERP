"""Frozen schema verifier; never examines business row values."""
import re
from ._reference_ddl import DDL

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
        raise RuntimeError("M16 reference incompatible engine/collation: " + table)
    expected = {}
    unique = set()
    primary = None
    for line in sql.splitlines()[1:]:
        line = line.strip().rstrip(",")
        if not line or line.startswith(("CONSTRAINT", ")")):
            continue
        match = re.match(
            r"(\w+)\s+(ENUM\([^)]*\)|VARCHAR\(\d+\)|CHAR\(\d+\)|BIGINT UNSIGNED|BIGINT|SMALLINT UNSIGNED|TINYINT UNSIGNED|DATETIME|TIMESTAMP|DATE|TEXT|BOOLEAN)(.*)",
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
        default = re.search(r"DEFAULT (CURRENT_TIMESTAMP|TRUE|FALSE|'[^']*'|[0-9]+)", tail)
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
            raise RuntimeError("M16 reference incompatible column collation: " + table)
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
        raise RuntimeError("M16 reference incompatible columns/defaults: " + table)
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
        raise RuntimeError("M16 reference incompatible foreign keys: " + table)
    cursor.execute(
        "SELECT INDEX_NAME,NON_UNIQUE,COLUMN_NAME,SUB_PART FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX",
        [table],
    )
    indexes = {}
    for name, non_unique, column, prefix in cursor.fetchall():
        if prefix is not None:
            raise RuntimeError(
                "M16 reference prefix indexes do not match canonical uniqueness: " + table
            )
        indexes.setdefault((name, non_unique), []).append(column)
    wanted = {(0, (primary,))} | {(0, columns) for columns in unique}
    for column, _, _ in fk:
        if not any(cols[0] == column for _, cols in wanted):
            wanted.add((1, (column,)))
    actual_unique = {tuple(cols) for (_, n), cols in indexes.items() if n == 0}
    expected_unique = {cols for n, cols in wanted if n == 0}
    if actual_unique != expected_unique or indexes.get(('PRIMARY', 0)) != [primary]:
        raise RuntimeError('M16 reference incompatible uniqueness: ' + table)
    # Subsequent named non-unique performance indexes may cover FK prefixes.
    if any(not any(cols[0] == column for cols in indexes.values()) for column, _, _ in fk):
        raise RuntimeError('M16 reference missing FK index: ' + table)
    cursor.execute(
        "SELECT DELETE_RULE,UPDATE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME=%s",
        [table],
    )
    if any(
        d not in ("RESTRICT", "NO ACTION") or u not in ("RESTRICT", "NO ACTION")
        for d, u in cursor.fetchall()
    ):
        raise RuntimeError("M16 reference unsafe foreign key actions: " + table)
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
        raise RuntimeError("M16 reference incompatible checks: " + table)
    return True


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        raise RuntimeError("M16 reference requires MySQL canonical schema.")
    with schema_editor.connection.cursor() as cursor:
        present = [verify(cursor, sql) for sql in DDL]
        for exists, sql in zip(present, DDL):
            if not exists:
                cursor.execute(sql)
        for sql in DDL:
            verify(cursor, sql)


def retain(apps, schema_editor):
    pass
