"""Prefect status CLI subcommand."""

from __future__ import annotations

import requests
from pydantic import BaseModel, ConfigDict
from rich.table import Table

from irsol_data_pipeline.cli.common import get_console, print_banner, print_json
from irsol_data_pipeline.cli.metadata import OutputFormat
from irsol_data_pipeline.prefect.config import (
    PREFECT_SERVER_HOST,
    PREFECT_SERVER_PORT,
    build_prefect_api_healthcheck_url,
    build_prefect_server_base_url,
)

DEFAULT_REQUEST_TIMEOUT_SECONDS = 5.0


class PrefectStatusReport(BaseModel):
    """Operator-facing status information for the local Prefect server.

    Attributes:
        dashboard_url: Base URL for the dashboard.
        detail: Human-readable status detail.
        healthcheck_url: URL used for the HTTP probe.
        host: Expected Prefect host.
        http_status: HTTP status code when available.
        port: Expected Prefect port.
        reachable: Whether the server answered successfully.
        status: Stable machine-readable status string.
    """

    model_config = ConfigDict(frozen=True)

    dashboard_url: str
    detail: str
    healthcheck_url: str
    host: str
    http_status: int | None
    port: int
    reachable: bool
    status: str


def _check_prefect_status(host: str, port: int) -> PrefectStatusReport:
    """Probe the local Prefect API health endpoint.

    Args:
        host: Prefect server host to probe.
        port: Prefect server port to probe.

    Returns:
        Structured status report for the expected local Prefect server.
    """

    dashboard_url = build_prefect_server_base_url(host, port)
    healthcheck_url = build_prefect_api_healthcheck_url(host, port)

    try:
        response = requests.get(
            healthcheck_url,
            timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return PrefectStatusReport(
            dashboard_url=dashboard_url,
            detail=str(exc),
            healthcheck_url=healthcheck_url,
            host=host,
            http_status=None,
            port=port,
            reachable=False,
            status="unreachable",
        )

    if response.ok:
        return PrefectStatusReport(
            dashboard_url=dashboard_url,
            detail="Prefect dashboard is reachable on the expected port.",
            healthcheck_url=healthcheck_url,
            host=host,
            http_status=response.status_code,
            port=port,
            reachable=True,
            status="running",
        )

    return PrefectStatusReport(
        dashboard_url=dashboard_url,
        detail=f"Health check returned HTTP {response.status_code}.",
        healthcheck_url=healthcheck_url,
        host=host,
        http_status=response.status_code,
        port=port,
        reachable=False,
        status="error",
    )


def _render_status_report(report: PrefectStatusReport) -> None:
    """Render the human-readable Prefect status table.

    Args:
        report: Status report to display.
    """

    title_style = "bold italic green" if report.reachable else "bold italic red"
    header_style = "bold green" if report.reachable else "bold red"
    status_style = "green" if report.reachable else "red"
    table = Table(
        title="Prefect Status",
        show_header=True,
        title_style=title_style,
        header_style=header_style,
    )
    table.add_column("Field", style="white", no_wrap=True)
    table.add_column("Value", style="white")
    table.add_row("Status", f"[{status_style}]{report.status}[/{status_style}]")
    table.add_row("Reachable", "yes" if report.reachable else "no")
    table.add_row("Host", report.host)
    table.add_row("Port", str(report.port))
    table.add_row("Dashboard URL", report.dashboard_url)
    table.add_row("Health Check", report.healthcheck_url)
    table.add_row(
        "HTTP Status",
        str(report.http_status) if report.http_status is not None else "-",
    )
    table.add_row("Detail", report.detail)
    get_console().print(table)


def status(
    format: OutputFormat = "table",
    no_banner: bool = False,
    host: str = PREFECT_SERVER_HOST,
    port: int = PREFECT_SERVER_PORT,
) -> int:
    """Check whether the local Prefect dashboard is reachable on its expected
    port.

    Args:
        format: Output format for the report.
        no_banner: Suppress the runtime banner.
        host: Prefect server host to probe.
        port: Prefect server port to probe.

    Returns:
        Zero when the local Prefect dashboard is reachable, otherwise one.
    """

    print_banner(output_format=format, no_banner=no_banner)

    report = _check_prefect_status(host=host, port=port)
    if format == "json":
        print_json(report.model_dump())
    else:
        _render_status_report(report)

    return 0 if report.reachable else 1
