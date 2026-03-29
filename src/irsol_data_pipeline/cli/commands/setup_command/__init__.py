"""Setup command group for configuring user and server Prefect profiles."""

from __future__ import annotations

from cyclopts import App

setup_app = App(
    name="setup",
    help="Configure local or server Prefect profiles.",
)

setup_app.command(
    "irsol_data_pipeline.cli.commands.setup_command.user_command:setup_user",
    name="user",
    help="(User) Configure your local Prefect client profile to connect to the shared server.",
)

setup_app.command(
    "irsol_data_pipeline.cli.commands.setup_command.server_command:setup_server",
    name="server",
    help="(Maintainer) Create or update the Prefect server profile with database and API settings.",
)
