import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

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
def run(
    contract: str = typer.Option(..., "--contract", "-c", help="Path or URL to contract YAML"),
    mode: str = typer.Option("block", "--mode", "-m", help="Enforcement mode: block|warn|log"),
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Server block to test"),
):
    """Run validation for a data contract."""
    from sraosha.core.engine import ContractEngine, ContractViolationError, EnforcementMode

    try:
        enforcement = EnforcementMode(mode)
    except ValueError:
        console.print(f"[red]Invalid mode: {mode}. Use block, warn, or log.[/red]")
        raise typer.Exit(1)

    engine = ContractEngine(contract_path=contract, enforcement_mode=enforcement, server=server)

    try:
        result = engine.run()
    except ContractViolationError as exc:
        console.print(f"[red]BLOCKED:[/red] {exc}")
        raise typer.Exit(1)

    status = "[green]PASSED[/green]" if result.passed else "[yellow]FAILED[/yellow]"
    console.print(f"{status} — {result.checks_passed}/{result.checks_total} checks passed")
    if result.failures:
        for f in result.failures:
            console.print(f"  [red]✗[/red] {f.get('check', '?')}: {f.get('message', '')}")


@app.command()
def status(
    format: str = typer.Option("table", "--format", "-f", help="Output format: table|json"),
):
    """Show status of all registered contracts (requires API)."""
    import httpx

    from sraosha.config import settings

    try:
        resp = httpx.get(
            f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/contracts",
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        console.print(f"[red]Failed to connect to API: {exc}[/red]")
        raise typer.Exit(1)

    if format == "json":
        console.print(json.dumps(data, indent=2))
        return

    table = Table(title="Registered Contracts")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Owner")
    table.add_column("Mode")
    table.add_column("Active")

    for item in data.get("items", []):
        table.add_row(
            item["contract_id"],
            item["title"],
            item.get("owner_team", "—"),
            item["enforcement_mode"],
            "Yes" if item["is_active"] else "No",
        )

    console.print(table)


@app.command()
def history(
    contract: str = typer.Option(..., "--contract", "-c", help="Contract ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of runs to show"),
):
    """Show run history for a contract (requires API)."""
    import httpx

    from sraosha.config import settings

    try:
        resp = httpx.get(
            f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/runs",
            params={"contract_id": contract, "limit": limit},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        console.print(f"[red]Failed to connect to API: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Run History: {contract}")
    table.add_column("Timestamp")
    table.add_column("Status")
    table.add_column("Checks")
    table.add_column("Duration")
    table.add_column("Triggered By")

    for item in data.get("items", []):
        style = "green" if item["status"] == "passed" else "red"
        table.add_row(
            item["run_at"],
            f"[{style}]{item['status']}[/{style}]",
            f"{item['checks_passed']}/{item['checks_total']}",
            f"{item.get('duration_ms', '—')}ms" if item.get("duration_ms") else "—",
            item.get("triggered_by", "—"),
        )

    console.print(table)


@app.command()
def register(
    contract: str = typer.Option(..., "--contract", "-c", help="Path to contract YAML"),
    team: str = typer.Option(..., "--team", "-t", help="Owner team name"),
):
    """Register a contract with the Sraosha API."""
    import httpx
    import yaml

    from sraosha.config import settings

    path = Path(contract)
    if not path.exists():
        console.print(f"[red]File not found: {contract}[/red]")
        raise typer.Exit(1)

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    base = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1"
    team_id: str | None = None
    try:
        tr = httpx.get(f"{base}/teams", timeout=10.0)
        tr.raise_for_status()
        for row in tr.json():
            if row.get("name") == team:
                team_id = row.get("id")
                break
        if not team_id:
            cr = httpx.post(f"{base}/teams", json={"name": team}, timeout=10.0)
            if cr.status_code in (200, 201):
                team_id = cr.json().get("id")
    except Exception:
        team_id = None

    payload = {
        "contract_id": data.get("id", path.stem),
        "title": data.get("info", {}).get("title", path.stem),
        "description": data.get("info", {}).get("description"),
        "file_path": str(path.resolve()),
        "team_id": team_id,
        "alerting_profile_id": None,
        "raw_yaml": raw,
        "enforcement_mode": data.get("x-sraosha", {}).get("enforcement_mode", "block"),
    }

    try:
        resp = httpx.post(
            f"{base}/contracts",
            json=payload,
            timeout=10.0,
        )
        if resp.status_code == 409:
            console.print("[yellow]Contract already registered.[/yellow]")
            return
        resp.raise_for_status()
        console.print(f"[green]Registered:[/green] {payload['contract_id']}")
    except Exception as exc:
        console.print(f"[red]Failed: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def impact(
    contract: str = typer.Option(..., "--contract", "-c", help="Contract ID"),
    fields: str = typer.Option(..., "--fields", "-f", help="Comma-separated field names"),
):
    """Show impact of a proposed change (requires API)."""
    import httpx

    from sraosha.config import settings

    field_list = [f.strip() for f in fields.split(",") if f.strip()]

    try:
        resp = httpx.post(
            f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/impact/{contract}/analyze",
            json={"changed_fields": field_list},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        console.print(f"[red]Failed to connect to API: {exc}[/red]")
        raise typer.Exit(1)

    severity_color = {"high": "red", "medium": "yellow", "low": "green"}.get(
        data["severity"], "white"
    )
    console.print(f"Severity: [{severity_color}]{data['severity'].upper()}[/{severity_color}]")
    console.print(f"Directly affected: {', '.join(data['directly_affected']) or 'None'}")
    console.print(f"Transitively affected: {', '.join(data['transitively_affected']) or 'None'}")


@app.command()
def serve(
    host: Optional[str] = typer.Option(None, "--host", help="Bind host"),
    port: Optional[int] = typer.Option(None, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the Sraosha API server and dashboard."""
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
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    console.print("[green]Database upgraded successfully.[/green]")


if __name__ == "__main__":
    app()
