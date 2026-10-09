import app.models  # noqa: F401  (register every table)
from alembic import context
from app.db.base import Base
from app.db.session import make_engine

target_metadata = Base.metadata


def _include(obj, name, type_, reflected, compare_to):
    # Views are managed in raw SQL inside migrations.
    return not (type_ == "table" and name.startswith("v_")) and name not in ("student_user_account", "employee_user_account")


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection") or make_engine()
    if hasattr(connectable, "connect") and not hasattr(connectable, "execute"):
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, compare_server_default=True,
                      include_object=_include, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; run against a database.")
run_migrations_online()
