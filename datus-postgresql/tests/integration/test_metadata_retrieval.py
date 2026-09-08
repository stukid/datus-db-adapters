# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

import uuid

import pytest

from datus_postgresql import PostgreSQLConnector

pytestmark = pytest.mark.integration


def test_ddl_preserves_composite_keys_and_standalone_unique_indexes(config):
    """Key order comes from constraints; index predicates and expressions must survive."""
    connector = PostgreSQLConnector(config)
    table_name = f"ddl_keys_{uuid.uuid4().hex[:8]}"
    table_ref = f'{connector.quote_identifier(config.schema_name)}."{table_name}"'
    index_prefix = f"{table_name}_index"
    statements = [
        f'CREATE TABLE {table_ref} (id INT, "Tenant ID" INT, email TEXT, active BOOLEAN, '
        'PRIMARY KEY ("Tenant ID", id), CONSTRAINT "Email Key" UNIQUE (email, "Tenant ID"))',
        f"CREATE UNIQUE INDEX {index_prefix}_plain ON {table_ref} (email, id)",
        f"CREATE UNIQUE INDEX {index_prefix}_partial ON {table_ref} (email) WHERE active",
        f"CREATE UNIQUE INDEX {index_prefix}_expression ON {table_ref} (lower(email))",
        f"CREATE INDEX {index_prefix}_ordinary ON {table_ref} (active)",
    ]
    try:
        for statement in statements:
            result = connector.execute_ddl(statement)
            assert result.success, result.error

        tables = connector.get_tables_with_ddl(schema_name=config.schema_name, tables=[table_name])

        assert [table["table_name"] for table in tables] == [table_name]
        definition = tables[0]["definition"]
        assert f'CONSTRAINT "{table_name}_pkey" PRIMARY KEY ("Tenant ID", id)' in definition
        assert 'CONSTRAINT "Email Key" UNIQUE (email, "Tenant ID")' in definition
        assert definition.count("CREATE UNIQUE INDEX") == 3
        assert f"{index_prefix}_plain" in definition and "USING btree (email, id);" in definition
        assert f"{index_prefix}_partial" in definition and "USING btree (email) WHERE active;" in definition
        assert f"{index_prefix}_expression" in definition and "USING btree (lower(email));" in definition
        assert f"{index_prefix}_ordinary" not in definition
    finally:
        try:
            dropped = connector.execute_ddl(f"DROP TABLE IF EXISTS {table_ref}")
            assert dropped.success, dropped.error
        finally:
            connector.close()
