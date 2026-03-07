import os
import psycopg
from psycopg import AsyncConnection
from typing import Dict, Any, List

async def run_rls_audit(db_url: str) -> Dict[str, Any]:
    """
    Executa uma auditoria completa de Row Level Security (RLS) no Supabase.
    Retorna um resumo de tabelas com e sem RLS habilitado.
    """
    audit_results = {
        "status": "success",
        "tables": [],
        "summary": {}
    }

    async with await AsyncConnection.connect(db_url) as conn:
        async with conn.cursor() as cur:
            sql_coverage = """
            WITH t AS (
              SELECT tablename, rowsecurity
              FROM pg_tables WHERE schemaname='public'
            )
            SELECT
              tablename,
              rowsecurity,
              (SELECT json_agg(json_build_object(
                'policy', policyname,
                'cmd', cmd,
                'roles', roles
              ))
               FROM pg_policies p
               WHERE p.tablename=t.tablename
               AND p.schemaname='public') AS policies
            FROM t
            ORDER BY rowsecurity DESC, tablename;
            """
            await cur.execute(sql_coverage)
            rows = await cur.fetchall()
            for row in rows:
                table_name, row_security, policies = row
                audit_results["tables"].append({
                    "tablename": table_name,
                    "rls_enabled": row_security,
                    "policies": policies or []
                })

            sql_summary = """
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE rowsecurity) AS enabled,
              COUNT(*) FILTER (WHERE NOT rowsecurity) AS disabled
            FROM pg_tables
            WHERE schemaname='public';
            """
            await cur.execute(sql_summary)
            summary_row = await cur.fetchone()
            if summary_row:
                audit_results["summary"] = {
                    "total_tables": summary_row[0],
                    "rls_enabled": summary_row[1],
                    "rls_disabled": summary_row[2]
                }

    return audit_results

async def run_schema_audit(db_url: str) -> Dict[str, Any]:
    """
    Executa uma auditoria de qualidade do esquema do banco de dados.
    Verifica chaves primárias ausentes e timestamps ausentes.
    """
    issues = {
        "missing_pks": [],
        "missing_fk_indexes": [],
        "missing_timestamps": []
    }

    async with await AsyncConnection.connect(db_url) as conn:
        async with conn.cursor() as cur:
            sql_no_pk = """
            SELECT table_name
            FROM information_schema.tables t
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_schema = t.table_schema
                  AND table_name = t.table_name
                  AND constraint_type = 'PRIMARY KEY'
              );
            """
            await cur.execute(sql_no_pk)
            issues["missing_pks"] = [r[0] for r in await cur.fetchall()]

            sql_no_ts = """
            SELECT table_name
            FROM information_schema.tables t
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
              AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = t.table_schema
                  AND table_name = t.table_name
                  AND column_name IN ('created_at', 'createdat')
              );
            """
            await cur.execute(sql_no_ts)
            issues["missing_timestamps"] = [r[0] for r in await cur.fetchall()]

    return issues
