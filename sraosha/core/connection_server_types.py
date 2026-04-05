"""Supported database `server_type` values for stored connections.

Extend this tuple when adding introspection and DQ support for additional sources.
"""

SUPPORTED_CONNECTION_SERVER_TYPES: tuple[str, ...] = (
    "postgres",
    "mysql",
    "bigquery",
    "clickhouse",
    "mssql",
    "motherduck",
    "presto",
    "oracle",
    "redshift",
    "snowflake",
    "trino",
)
