"""
Database setup and management script.

Usage:
    uv run python scripts/db_setup.py init      # Initialize database
    uv run python scripts/db_setup.py migrate   # Run migrations
    uv run python scripts/db_setup.py reset     # Reset database (WARNING: deletes all data)
    uv run python scripts/db_setup.py status    # Check migration status
"""

from __future__ import annotations

import asyncio
import sys

import typer
from rich.console import Console
from rich.panel import Panel

from core.config import settings
from database.session import close_db, get_engine, init_db

app = typer.Typer()
console = Console()


@app.command()
def init() -> None:
    """
    Initialize database with pgvector extension and tables.

    This will:
    1. Install pgvector extension
    2. Create all tables
    """
    console.print(
        Panel.fit(
            "[bold blue]Initializing database...[/bold blue]",
            title="Database Setup",
        )
    )

    if settings.STORAGE_BACKEND != "postgresql":
        console.print(
            "[yellow]Warning: STORAGE_BACKEND is not set to 'postgresql'[/yellow]"
        )
        console.print(f"Current backend: {settings.STORAGE_BACKEND}")
        if not typer.confirm("Continue anyway?"):
            raise typer.Abort()

    if not settings.DATABASE_URL:
        console.print("[red]Error: DATABASE_URL not configured[/red]")
        raise typer.Exit(1)

    async def _init() -> None:
        try:
            await init_db()
            console.print("[green]✓ Database initialized successfully[/green]")
            console.print("\nCreated tables:")
            console.print("  - documents")
            console.print("  - entities")
            console.print("  - graph_relations")
            console.print("\nInstalled extensions:")
            console.print("  - vector (pgvector)")

        except Exception as e:
            console.print(f"[red]✗ Failed to initialize database: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await close_db()

    asyncio.run(_init())


@app.command()
def migrate() -> None:
    """
    Run Alembic migrations.

    Equivalent to: alembic upgrade head
    """
    import subprocess

    console.print(
        Panel.fit(
            "[bold blue]Running database migrations...[/bold blue]",
            title="Alembic Migrations",
        )
    )

    result = subprocess.run(["alembic", "upgrade", "head"], check=False)

    if result.returncode == 0:
        console.print("[green]✓ Migrations completed successfully[/green]")
    else:
        console.print("[red]✗ Migration failed[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """
    Check current migration status.

    Equivalent to: alembic current
    """
    import subprocess

    console.print(
        Panel.fit(
            "[bold blue]Checking migration status...[/bold blue]",
            title="Migration Status",
        )
    )

    subprocess.run(["alembic", "current"], check=False)


@app.command()
def reset() -> None:
    """
    Reset database (WARNING: deletes all data).

    This will:
    1. Drop all tables
    2. Recreate tables
    """
    console.print(
        Panel.fit(
            "[bold red]WARNING: This will delete ALL data![/bold red]",
            title="Database Reset",
        )
    )

    if not typer.confirm("Are you sure you want to reset the database?"):
        raise typer.Abort()

    if not typer.confirm("This action cannot be undone. Continue?"):
        raise typer.Abort()

    async def _reset() -> None:
        from database.base import Base

        engine = get_engine()

        try:
            async with engine.begin() as conn:
                # Drop all tables
                await conn.run_sync(Base.metadata.drop_all)
                console.print("[yellow]✓ Dropped all tables[/yellow]")

                # Recreate tables
                await conn.run_sync(Base.metadata.create_all)
                console.print("[green]✓ Recreated all tables[/green]")

            console.print("\n[green]Database reset complete[/green]")

        except Exception as e:
            console.print(f"[red]✗ Failed to reset database: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await close_db()

    asyncio.run(_reset())


@app.command()
def info() -> None:
    """Show database configuration information."""
    console.print(
        Panel.fit(
            "[bold blue]Database Configuration[/bold blue]",
            title="Info",
        )
    )

    console.print(f"Storage Backend: [cyan]{settings.STORAGE_BACKEND}[/cyan]")

    if settings.STORAGE_BACKEND == "postgresql":
        if settings.DATABASE_URL:
            # Hide password in URL
            url = settings.DATABASE_URL
            if "@" in url:
                prefix, suffix = url.split("@", 1)
                if ":" in prefix:
                    user_part, _ = prefix.rsplit(":", 1)
                    masked_url = f"{user_part}:****@{suffix}"
                else:
                    masked_url = url
            else:
                masked_url = url

            console.print(f"Database URL: [green]{masked_url}[/green]")
            console.print(f"Pool Size: {settings.DATABASE_POOL_SIZE}")
            console.print(f"Max Overflow: {settings.DATABASE_MAX_OVERFLOW}")
        else:
            console.print("[red]Database URL: Not configured[/red]")

    elif settings.STORAGE_BACKEND == "local":
        console.print(f"Working Dir: [green]{settings.LIGHTRAG_WORKING_DIR}[/green]")
        console.print(f"Workspace: [green]{settings.LIGHTRAG_WORKSPACE}[/green]")

    console.print(f"\nLightRAG Embedding Dim: {settings.LIGHTRAG_EMBEDDING_DIM}")


if __name__ == "__main__":
    app()
