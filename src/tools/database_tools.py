from langchain_core.tools import tool
from src.utils.supabase_utils import run_rls_audit, run_schema_audit
from src.config import settings

@tool
async def audit_supabase_security():
    """
    Executa uma auditoria de segurança no banco de dados Supabase.
    Verifica Row Level Security (RLS) em todas as tabelas e reporta riscos.
    """
    if not settings.SUPABASE_DATABASE_URL:
        return "Erro: SUPABASE_DATABASE_URL não configurada."

    results = await run_rls_audit(settings.SUPABASE_DATABASE_URL)
    summary = results["summary"]

    report = "### Relatório de Auditoria RLS\n"
    report += f"- Total de Tabelas: {summary['total_tables']}\n"
    report += f"- RLS Habilitado: {summary['rls_enabled']} ✅\n"
    report += f"- RLS Desabilitado: {summary['rls_disabled']} ❌ (RISCO DE SEGURANÇA)\n\n"

    if summary['rls_disabled'] > 0:
        report += "#### Tabelas em Risco:\n"
        for t in results["tables"]:
            if not t["rls_enabled"]:
                report += f"- {t['tablename']}\n"

    return report

@tool
async def audit_database_schema():
    """
    Executa uma auditoria de integridade do esquema do banco de dados.
    Detecta chaves primárias ausentes e falta de timestamps de auditoria (created_at).
    """
    if not settings.SUPABASE_DATABASE_URL:
        return "Erro: SUPABASE_DATABASE_URL não configurada."

    issues = await run_schema_audit(settings.SUPABASE_DATABASE_URL)

    report = "### Relatório de Integridade de Esquema\n"

    if issues["missing_pks"]:
        report += f"❌ Tabelas sem Chave Primária: {', '.join(issues['missing_pks'])}\n"
    else:
        report += "✅ Todas as tabelas possuem Chave Primária.\n"

    if issues["missing_timestamps"]:
        report += f"⚠️ Tabelas sem 'created_at': {', '.join(issues['missing_timestamps'])}\n"
    else:
        report += "✅ Todas as tabelas possuem timestamps de auditoria.\n"

    return report
