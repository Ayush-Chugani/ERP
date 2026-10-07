import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
@pytest.mark.django_db(transaction=True)
def test_feedback_rollback_forward_on_isolated_database():
    assert connection.settings_dict['NAME'].startswith('test_')
    executor=MigrationExecutor(connection)
    leaf=executor.loader.graph.leaf_nodes('feedback')
    try:
        executor.migrate([('feedback',None)])
        assert 'feedback_response_item_choice' not in connection.introspection.table_names()
    finally:MigrationExecutor(connection).migrate(leaf)
    assert 'feedback_response_item_choice' in connection.introspection.table_names()
