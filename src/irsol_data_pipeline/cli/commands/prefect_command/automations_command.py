"""Prefect automations CLI subcommands."""

from __future__ import annotations

from dataclasses import dataclass

from cyclopts import App
from rich.table import Table

from irsol_data_pipeline.cli.common import (
    get_console,
    print_json,
)
from irsol_data_pipeline.cli.metadata import OutputFormat
from irsol_data_pipeline.prefect.automations import (
    delete_pending_flows_automation,
    zombie_flow_automation,
)

automations_app = App(name="automations", help="List and configure Prefect automations.")


@dataclass(frozen=True)
class AutomationReportEntry:
    """Operator-facing result for one Prefect automation.

    Attributes:
        name: Automation name.
        description: Human-readable description.
        registered: Whether the automation is currently registered on the server.
    """

    name: str
    description: str
    registered: bool


def _get_automation_entries() -> list[AutomationReportEntry]:
    """Collect the current automation report entries.

    Queries the Prefect server for each known automation and reports its status.

    Returns:
        Current automation report entries.
    """

    from prefect.automations import Automation

    known_automations = [zombie_flow_automation, delete_pending_flows_automation]
    entries: list[AutomationReportEntry] = []
    for automation in known_automations:
        try:
            Automation.read(name=automation.name)
            registered = True
        except Exception:
            registered = False
        entries.append(
            AutomationReportEntry(
                name=automation.name,
                description=automation.description or "",
                registered=registered,
            )
        )
    return entries


def _render_automation_entries(entries: list[AutomationReportEntry]) -> None:
    """Render automation entries as a Rich table.

    Args:
        entries: Automation report entries to display.
    """

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Automation", style="white", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Registered", style="magenta", no_wrap=True)

    for entry in entries:
        table.add_row(
            entry.name,
            entry.description,
            "yes" if entry.registered else "no",
        )

    get_console().print(table)


def _serialize_automation_entries(
    entries: list[AutomationReportEntry],
) -> dict[str, object]:
    """Convert automation entries to stable JSON output.

    Args:
        entries: Automation report entries.

    Returns:
        JSON-serializable automation payload.
    """

    return {
        "automations": [
            {
                "name": entry.name,
                "description": entry.description,
                "registered": entry.registered,
            }
            for entry in entries
        ]
    }


@automations_app.command(name="list")
def list_automations(
    format: OutputFormat = "table",
) -> None:
    """List built-in automation definitions and their server registration status.

    Args:
        format: Output format for the report.
    """

    entries = _get_automation_entries()
    if format == "json":
        print_json(_serialize_automation_entries(entries))
        return

    _render_automation_entries(entries)


@automations_app.command(name="configure")
def configure_automations() -> int:
    """Register or update the built-in Prefect automations on the server.

    Requires a running Prefect server reachable at the configured API URL.

    Returns:
        Exit code for the command.
    """

    from prefect.automations import Automation

    automations: list[Automation] = [
        zombie_flow_automation,
        delete_pending_flows_automation,
    ]

    failed_count = 0
    for i, automation in enumerate(automations, start=1):
        total = len(automations)
        print(f"[{i}/{total}] Registering automation '{automation.name}'")
        try:
            existing_automation: Automation = Automation.read(name=automation.name)
        except Exception:
            try:
                automation.create()
                print(f"  v Automation '{automation.name}' registered successfully.")
            except Exception as exc:
                print(f"  x Failed to register '{automation.name}': {exc}")
                failed_count += 1
        else:
            try:
                existing_automation.name = automation.name
                existing_automation.description = automation.description
                existing_automation.trigger = automation.trigger
                existing_automation.actions = automation.actions
                existing_automation.update()
                print(f"  v Automation '{automation.name}' updated successfully.")
            except Exception as exc:
                print(f"  x Failed to update '{automation.name}': {exc}")
                failed_count += 1

    print()
    total = len(automations)
    succeeded = total - failed_count
    print(f"Summary: {succeeded} configured, {failed_count} failed")

    return 3 if failed_count > 0 else 0
