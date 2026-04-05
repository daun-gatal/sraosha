import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

import sraosha

app = typer.Typer(
    name="sraosha",
    help="Sraosha — The enforcement and governance runtime for data contracts.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def _main(
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to .sraosha config file (or set SRAOSHA_CONFIG).",
    ),
):
    """Global options applied before any subcommand."""
    if config:
        from sraosha.config import reload_settings

        reload_settings(config)


@app.command()
def version():
    """Show the Sraosha version."""
    console.print(f"sraosha {sraosha.__version__}")


@app.command()
def serve(
    host: Optional[str] = typer.Option(None, "--host", help="Bind host"),
    port: Optional[int] = typer.Option(None, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the Sraosha API server (JSON API + optional built SPA at /app/)."""
    import uvicorn

    from sraosha.config import settings

    uvicorn.run(
        "sraosha.api.app:create_app",
        factory=True,
        host=host or settings.API_HOST,
        port=port or settings.API_PORT,
        reload=reload,
    )


@app.command()
def worker(
    loglevel: str = typer.Option("info", "--loglevel", help="Celery log level."),
    concurrency: int = typer.Option(
        4,
        "--concurrency",
        "-c",
        help="Number of worker processes/threads.",
    ),
    hostname: Optional[str] = typer.Option(
        None,
        "--hostname",
        "-n",
        help="Worker hostname (use distinct values for multiple workers, e.g. w1@%%h).",
    ),
    queues: Optional[str] = typer.Option(
        None,
        "--queues",
        "-Q",
        help="Comma-separated queue names (default: Celery default queue).",
    ),
):
    """Run a Celery worker. Use one `sraosha beat` plus workers with distinct `--hostname`."""
    cmd = [
        "celery",
        "-A",
        "sraosha.tasks.celery_app",
        "worker",
        f"--loglevel={loglevel}",
        f"--concurrency={concurrency}",
    ]
    if hostname:
        cmd.append(f"--hostname={hostname}")
    if queues:
        cmd.extend(["-Q", queues])
    try:
        os.execvp(cmd[0], cmd)
    except OSError as exc:
        console.print(f"[red]Failed to start worker: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def beat(
    loglevel: str = typer.Option("info", "--loglevel", help="Celery beat log level."),
):
    """Run Celery beat. Use a single beat process with one or more workers."""
    cmd = ["celery", "-A", "sraosha.tasks.celery_app", "beat", f"--loglevel={loglevel}"]
    try:
        os.execvp(cmd[0], cmd)
    except OSError as exc:
        console.print(f"[red]Failed to start beat: {exc}[/red]")
        raise typer.Exit(1)


@app.command("db")
def db_upgrade():
    """Run database migrations (Alembic upgrade head)."""
    from alembic import command
    from alembic.config import Config

    ini_path = Path(sraosha.__file__).resolve().parent / "alembic.ini"
    if not ini_path.is_file():
        console.print(f"[red]Alembic config not found at {ini_path} (incomplete install?).[/red]")
        raise typer.Exit(1)
    alembic_cfg = Config(str(ini_path))
    command.upgrade(alembic_cfg, "head")
    console.print("[green]Database upgraded successfully.[/green]")


if __name__ == "__main__":
    app()
