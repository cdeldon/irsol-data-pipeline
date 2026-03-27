"""Tests for the prefect automations command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from irsol_data_pipeline.cli import app
from irsol_data_pipeline.cli.commands.prefect_command.automations_command import (
    AutomationReportEntry,
    configure_automations,
    list_automations,
)


class TestListAutomations:
    def test_list_automations_table_shows_registered(self, capsys: pytest.CaptureFixture[str]) -> None:
        mock_automation = MagicMock()
        mock_automation.name = "Crash zombie flows"
        mock_automation.description = "Some description"

        with (
            patch(
                "prefect.automations.Automation.read",
                return_value=mock_automation,
            ),
            patch(
                "irsol_data_pipeline.cli.commands.prefect_command.automations_command._render_automation_entries"
            ) as mock_render,
        ):
            list_automations()

        mock_render.assert_called_once()
        entries: list[AutomationReportEntry] = mock_render.call_args[0][0]
        assert all(e.registered for e in entries)

    def test_list_automations_table_shows_unregistered_on_server_error(self) -> None:
        with (
            patch(
                "prefect.automations.Automation.read",
                side_effect=RuntimeError("not found"),
            ),
            patch(
                "irsol_data_pipeline.cli.commands.prefect_command.automations_command._render_automation_entries"
            ) as mock_render,
        ):
            list_automations()

        entries: list[AutomationReportEntry] = mock_render.call_args[0][0]
        assert all(not e.registered for e in entries)

    def test_list_automations_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        mock_automation = MagicMock()
        mock_automation.name = "Crash zombie flows"
        mock_automation.description = "desc"

        with patch(
            "prefect.automations.Automation.read",
            return_value=mock_automation,
        ):
            app(
                ["prefect", "automations", "list", "--format", "json"],
                exit_on_error=False,
                print_error=False,
                result_action="return_value",
            )

        payload = json.loads(capsys.readouterr().out)
        assert "automations" in payload
        assert len(payload["automations"]) == 2
        assert payload["automations"][0]["registered"] is True

    def test_list_automations_json_unregistered(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch(
            "prefect.automations.Automation.read",
            side_effect=RuntimeError("not found"),
        ):
            app(
                ["prefect", "automations", "list", "--format", "json"],
                exit_on_error=False,
                print_error=False,
                result_action="return_value",
            )

        payload = json.loads(capsys.readouterr().out)
        assert all(not a["registered"] for a in payload["automations"])


class TestConfigureAutomations:
    def test_creates_automations_when_not_registered(self) -> None:
        with (
            patch(
                "prefect.automations.Automation.read",
                side_effect=RuntimeError("not found"),
            ),
            patch(
                "irsol_data_pipeline.cli.commands.prefect_command.automations_command.zombie_flow_automation"
            ) as mock_zombie,
            patch(
                "irsol_data_pipeline.cli.commands.prefect_command.automations_command.delete_pending_flows_automation"
            ) as mock_delete,
            patch("builtins.print"),
        ):
            result = configure_automations()

        assert result == 0
        mock_zombie.create.assert_called_once()
        mock_delete.create.assert_called_once()

    def test_updates_automations_when_already_registered(self) -> None:
        mock_existing = MagicMock()

        with (
            patch(
                "prefect.automations.Automation.read",
                return_value=mock_existing,
            ),
            patch("builtins.print"),
        ):
            result = configure_automations()

        assert result == 0
        assert mock_existing.update.call_count == 2

    def test_returns_exit_code_3_on_create_failure(self) -> None:
        with (
            patch(
                "prefect.automations.Automation.read",
                side_effect=RuntimeError("not found"),
            ),
            patch(
                "irsol_data_pipeline.cli.commands.prefect_command.automations_command.zombie_flow_automation"
            ) as mock_zombie,
            patch(
                "irsol_data_pipeline.cli.commands.prefect_command.automations_command.delete_pending_flows_automation"
            ) as mock_delete,
            patch("builtins.print"),
        ):
            mock_zombie.create.side_effect = RuntimeError("server error")
            mock_delete.create.side_effect = RuntimeError("server error")
            result = configure_automations()

        assert result == 3

    def test_returns_exit_code_3_on_update_failure(self) -> None:
        mock_existing = MagicMock()
        mock_existing.update.side_effect = RuntimeError("update failed")

        with (
            patch(
                "prefect.automations.Automation.read",
                return_value=mock_existing,
            ),
            patch("builtins.print"),
        ):
            result = configure_automations()

        assert result == 3

    def test_configure_automations_via_app(self) -> None:
        mock_existing = MagicMock()

        with (
            patch(
                "prefect.automations.Automation.read",
                return_value=mock_existing,
            ),
            patch("builtins.print"),
        ):
            result = app(
                ["prefect", "automations", "configure"],
                exit_on_error=False,
                print_error=False,
                result_action="return_value",
            )

        assert result == 0
