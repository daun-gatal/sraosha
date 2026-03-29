import json
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
def drift(
    contract: str = typer.Option(..., "--contract", "-c", help="Contract ID"),
):
    """Show current drift status for a contract (requires API)."""
    import httpx

    from sraosha.config import settings

    try:
        resp = httpx.get(
            f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/drift/{contract}",
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        console.print(f"[red]Failed to connect to API: {exc}[/red]")
        raise typer.Exit(1)

    if not data:
        console.print("No drift data for this contract.")
        return

    table = Table(title=f"Drift Status: {contract}")
    table.add_column("Metric")
    table.add_column("Table.Column")
    table.add_column("Value")
    table.add_column("Warning")
    table.add_column("Breach")
    table.add_column("Status")

    for m in data:
        col = f"{m['table_name']}.{m.get('column_name', '—')}"
        status_str = ""
        if m.get("is_breached"):
            status_str = "[red]BREACHED[/red]"
        elif m.get("is_warning"):
            status_str = "[yellow]WARNING[/yellow]"
        else:
            status_str = "[green]OK[/green]"

        table.add_row(
            m["metric_type"],
            col,
            f"{m['value']:.4f}",
            f"{m.get('warning_threshold', '—')}",
            f"{m.get('breach_threshold', '—')}",
            status_str,
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

    payload = {
        "contract_id": data.get("id", path.stem),
        "title": data.get("info", {}).get("title", path.stem),
        "description": data.get("info", {}).get("description"),
        "file_path": str(path.resolve()),
        "owner_team": team,
        "raw_yaml": raw,
        "enforcement_mode": data.get("x-sraosha", {}).get("enforcement_mode", "block"),
    }

    try:
        resp = httpx.post(
            f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/contracts",
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
    console.print(
        f"Transitively affected: {', '.join(data['transitively_affected']) or 'None'}"
    )


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the Sraosha API server."""
    import uvicorn

    uvicorn.run(
        "sraosha.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


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
