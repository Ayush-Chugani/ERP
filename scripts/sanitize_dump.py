"""Make a mysqldump safe to share: strip DEFINER clauses and blank every password hash.

Usage: python scripts/sanitize_dump.py <main.sql> <empty-tables.sql> <output.sql>
"""

import re
import sys

HEADER = (
    "-- SIMS sample database (schema, triggers, views and synthetic sample data).\n"
    "-- Passwords are blanked and session/token/login-audit rows are excluded.\n"
    "-- Import with scripts/import-database.ps1 (see TEAM_SETUP.md).\n"
)


def sanitize(text: str) -> str:
    text = re.sub(r"/\*!\d+ DEFINER=`[^`]*`@`[^`]*`\s*\*/\s*", "", text)
    text = re.sub(r"DEFINER=`[^`]*`@`[^`]*`\s*", "", text)
    text = re.sub(r"/\*!\d+ SQL SECURITY DEFINER \*/\s*", "", text)
    # "!" is Django's marker for an unusable password.
    return re.sub(r"'(?:pbkdf2_sha256|argon2|bcrypt|md5)[$][^']*'", "'!'", text)


def main(main_path: str, empty_path: str, out_path: str) -> None:
    read = lambda p: open(p, encoding="utf-8", errors="surrogateescape").read()  # noqa: E731
    sql = sanitize(read(main_path) + "\n" + read(empty_path))
    if re.search(r"DEFINER|pbkdf2_sha256", sql):
        raise SystemExit("Sanitising failed: sensitive markers remain.")
    with open(out_path, "w", encoding="utf-8", errors="surrogateescape") as out:
        out.write(HEADER + sql)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
