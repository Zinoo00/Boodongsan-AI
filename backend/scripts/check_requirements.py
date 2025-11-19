"""
Check system requirements for storage backends.

Usage:
    uv run python scripts/check_requirements.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def check_postgresql_requirements() -> dict[str, bool]:
    """Check PostgreSQL backend requirements."""
    results = {}

    # Check asyncpg
    try:
        import asyncpg  # noqa: F401

        results["asyncpg"] = True
    except ImportError:
        results["asyncpg"] = False

    # Check psycopg
    try:
        import psycopg  # noqa: F401

        results["psycopg"] = True
    except ImportError:
        results["psycopg"] = False

    # Check SQLAlchemy
    try:
        import sqlalchemy  # noqa: F401

        results["sqlalchemy"] = True
    except ImportError:
        results["sqlalchemy"] = False

    # Check Alembic
    try:
        import alembic  # noqa: F401

        results["alembic"] = True
    except ImportError:
        results["alembic"] = False

    # Check pgvector
    try:
        import pgvector  # noqa: F401

        results["pgvector"] = True
    except ImportError:
        results["pgvector"] = False

    return results


def check_local_requirements() -> dict[str, bool]:
    """Check Local backend requirements."""
    results = {}

    # Check NetworkX
    try:
        import networkx  # noqa: F401

        results["networkx"] = True
    except ImportError:
        results["networkx"] = False

    # Check LightRAG
    try:
        import lightrag  # noqa: F401

        results["lightrag"] = True
    except ImportError:
        results["lightrag"] = False

    return results


def check_storage_directory() -> dict[str, bool]:
    """Check storage directory."""
    from core.config import settings

    results = {}

    # Check working directory
    working_dir = Path(settings.LIGHTRAG_WORKING_DIR) / settings.LIGHTRAG_WORKSPACE
    results["working_dir_exists"] = working_dir.exists()
    results["working_dir_writable"] = (
        working_dir.is_dir() and Path(settings.LIGHTRAG_WORKING_DIR).parent.exists()
    )

    return results


def check_database_connection() -> dict[str, bool]:
    """Check database connection (if PostgreSQL)."""
    from core.config import settings

    results = {}

    if settings.STORAGE_BACKEND == "postgresql":
        results["database_url_configured"] = bool(settings.DATABASE_URL)

        if settings.DATABASE_URL:
            # Try to connect
            import asyncio

            async def _test_connection() -> bool:
                try:
                    from database.session import get_engine

                    engine = get_engine()
                    async with engine.begin() as conn:
                        await conn.execute("SELECT 1")
                    return True
                except Exception:
                    return False

            try:
                results["database_connection"] = asyncio.run(_test_connection())
            except Exception:
                results["database_connection"] = False
        else:
            results["database_connection"] = False
    else:
        results["database_url_configured"] = True
        results["database_connection"] = True

    return results


def main() -> None:
    """Run all checks and display results."""
    from core.config import settings

    console.print(
        Panel.fit(
            "[bold blue]Storage Backend Requirements Check[/bold blue]",
            title="System Check",
        )
    )

    console.print(f"\nCurrent Storage Backend: [cyan]{settings.STORAGE_BACKEND}[/cyan]\n")

    # Check PostgreSQL requirements
    pg_results = check_postgresql_requirements()
    pg_table = Table(title="PostgreSQL Backend Requirements")
    pg_table.add_column("Package", style="cyan")
    pg_table.add_column("Status", style="bold")

    for package, installed in pg_results.items():
        status = "[green]✓ Installed[/green]" if installed else "[red]✗ Missing[/red]"
        pg_table.add_row(package, status)

    console.print(pg_table)

    # Check Local requirements
    local_results = check_local_requirements()
    local_table = Table(title="\nLocal Backend Requirements")
    local_table.add_column("Package", style="cyan")
    local_table.add_column("Status", style="bold")

    for package, installed in local_results.items():
        status = "[green]✓ Installed[/green]" if installed else "[red]✗ Missing[/red]"
        local_table.add_row(package, status)

    console.print(local_table)

    # Check storage directory
    storage_results = check_storage_directory()
    storage_table = Table(title="\nStorage Directory")
    storage_table.add_column("Check", style="cyan")
    storage_table.add_column("Status", style="bold")

    for check, passed in storage_results.items():
        status = "[green]✓ OK[/green]" if passed else "[yellow]⚠ Warning[/yellow]"
        storage_table.add_row(check.replace("_", " ").title(), status)

    console.print(storage_table)

    # Check database connection
    console.print("\n[bold]Checking database connection...[/bold]")
    db_results = check_database_connection()
    db_table = Table(title="Database Connection")
    db_table.add_column("Check", style="cyan")
    db_table.add_column("Status", style="bold")

    for check, passed in db_results.items():
        status = "[green]✓ OK[/green]" if passed else "[red]✗ Failed[/red]"
        db_table.add_row(check.replace("_", " ").title(), status)

    console.print(db_table)

    # Summary
    console.print("\n" + "=" * 60)

    if settings.STORAGE_BACKEND == "postgresql":
        all_pg_ok = all(pg_results.values())
        all_db_ok = all(db_results.values())

        if all_pg_ok and all_db_ok:
            console.print("[bold green]✓ All PostgreSQL requirements met![/bold green]")
        else:
            console.print(
                "[bold red]✗ Some PostgreSQL requirements are missing[/bold red]"
            )
            if not all_pg_ok:
                console.print("\nInstall missing packages:")
                console.print("  uv sync")
            if not all_db_ok:
                console.print("\nConfigure database:")
                console.print("  1. Set DATABASE_URL in .env")
                console.print("  2. Ensure PostgreSQL is running")
                console.print("  3. Run: uv run python scripts/db_setup.py init")
            sys.exit(1)

    elif settings.STORAGE_BACKEND == "local":
        all_local_ok = all(local_results.values())
        all_storage_ok = storage_results.get("working_dir_writable", False)

        if all_local_ok and all_storage_ok:
            console.print("[bold green]✓ All Local requirements met![/bold green]")
        else:
            console.print("[bold red]✗ Some Local requirements are missing[/bold red]")
            if not all_local_ok:
                console.print("\nInstall missing packages:")
                console.print("  uv sync")
            if not all_storage_ok:
                console.print("\nCheck storage directory permissions")
            sys.exit(1)

    console.print("\n[bold green]System is ready to run![/bold green]")


if __name__ == "__main__":
    main()
