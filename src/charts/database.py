"""
Graphyard Database Connector

Connects to the graphyard PostgreSQL database on the studio host.
Adapted from graphyard's shared/database.py but returns polars DataFrames.
"""

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

import polars as pl
import psycopg2
from psycopg2.extensions import connection as PgConnection


@dataclass
class GraphyardDB:
    """Connection manager for the graphyard PostgreSQL database.

    Usage:
        db = GraphyardDB.from_env()
        df = db.query("SELECT year, value FROM public.country_data LIMIT 10")
        schemas = db.list_schemas()
    """

    host: str = "192.168.4.50"
    port: int = 5432
    database: str = "graphyard"
    user: str = "postgres"
    password: str = "postgres"

    @classmethod
    def from_env(cls) -> "GraphyardDB":
        """Create config from GRAPHYARD_DB_* environment variables."""
        return cls(
            host=os.getenv("GRAPHYARD_DB_HOST", "192.168.4.50"),
            port=int(os.getenv("GRAPHYARD_DB_PORT", "5432")),
            database=os.getenv("GRAPHYARD_DB_NAME", "graphyard"),
            user=os.getenv("GRAPHYARD_DB_USER", "postgres"),
            password=os.getenv("GRAPHYARD_DB_PASSWORD", "postgres"),
        )

    def _connect(self) -> PgConnection:
        """Get a raw database connection."""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
        )

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def query(self, sql: str, params: Optional[tuple] = None) -> pl.DataFrame:
        """Execute a query and return results as a polars DataFrame.

        Args:
            sql: SQL query string. Use %s for parameter placeholders.
            params: Optional tuple of parameter values.

        Returns:
            polars.DataFrame with query results.
        """
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            if cur.description is None:
                return pl.DataFrame()

            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            if not rows:
                # Return empty DataFrame with correct column names
                return pl.DataFrame(
                    {col: [] for col in columns}
                )

            # Build column-oriented dict for polars
            data = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
            return pl.DataFrame(data)

    def query_single(self, sql: str, params: Optional[tuple] = None):
        """Execute a query and return a single scalar value."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            result = cur.fetchone()
            return result[0] if result else None

    def execute(self, sql: str, params: Optional[tuple] = None) -> None:
        """Execute a statement with no return value."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            conn.commit()

    def list_schemas(self) -> list[str]:
        """List all non-system schemas in the database."""
        df = self.query("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        return df["schema_name"].to_list()

    def list_tables(self, schema: str = "public") -> list[dict]:
        """List tables in a schema with row counts.

        Returns list of dicts with 'table_name' and 'row_estimate' keys.
        """
        df = self.query("""
            SELECT
                t.table_name,
                COALESCE(s.n_live_tup, 0) as row_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s
                ON s.schemaname = t.table_schema
                AND s.relname = t.table_name
            WHERE t.table_schema = %s
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """, (schema,))
        return df.to_dicts()

    def describe_table(self, table: str, schema: str = "public") -> pl.DataFrame:
        """Get column info for a table."""
        return self.query("""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))

    def test_connection(self) -> bool:
        """Test that the database is reachable."""
        try:
            result = self.query_single("SELECT 1")
            return result == 1
        except Exception:
            return False
