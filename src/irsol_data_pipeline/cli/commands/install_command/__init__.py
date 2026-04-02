"""Install command group for registering pipeline services."""

from __future__ import annotations

from cyclopts import App

install_app = App(
    name="install",
    help="Install pipeline components as system services.",
)

install_app.command(
    "irsol_data_pipeline.cli.commands.install_command.service_command:install_service",
    name="service",
    help="Interactively generate and install systemd service unit files for the pipeline.",
)
