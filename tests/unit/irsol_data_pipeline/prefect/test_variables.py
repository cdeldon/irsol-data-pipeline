"""Tests for Prefect variable resolution helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from irsol_data_pipeline.exceptions import DatasetRootNotConfiguredError
from irsol_data_pipeline.prefect.variables import (
    resolve_dataset_roots,
)


class TestResolveDatasetRoots:
    def test_returns_single_explicit_root(self) -> None:
        result = resolve_dataset_roots(("/tmp/dataset",))

        assert result == [Path("/tmp/dataset")]

    def test_parses_comma_separated_roots(self) -> None:
        result = resolve_dataset_roots(("/srv/data1", "/srv/data2", "/srv/data3"))

        assert result == [Path("/srv/data1"), Path("/srv/data2"), Path("/srv/data3")]

    def test_strips_whitespace_around_paths(self) -> None:
        result = resolve_dataset_roots((" /srv/data1 ", " /srv/data2 "))

        assert result == [Path("/srv/data1"), Path("/srv/data2")]

    def test_ignores_empty_segments(self) -> None:
        result = resolve_dataset_roots(("/srv/data1", "", "/srv/data2"))

        assert result == [Path("/srv/data1"), Path("/srv/data2")]

    @pytest.mark.parametrize("empty_roots", [None, tuple(), ("", "   ")])
    def test_falls_back_to_prefect_variable_when_empty(self, empty_roots) -> None:
        with patch(
            "irsol_data_pipeline.prefect.variables.get_variable",
            return_value="/srv/data",
        ):
            result = resolve_dataset_roots(empty_roots)

        assert result == [Path("/srv/data")]

    def test_parses_comma_separated_from_prefect_variable(self) -> None:
        with patch(
            "irsol_data_pipeline.prefect.variables.get_variable",
            return_value="/srv/data1,/srv/data2",
        ):
            result = resolve_dataset_roots(None)

        assert result == [Path("/srv/data1"), Path("/srv/data2")]

    def test_raises_when_neither_roots_nor_variable_are_available(self) -> None:
        with (
            patch(
                "irsol_data_pipeline.prefect.variables.get_variable",
                return_value="",
            ),
            pytest.raises(DatasetRootNotConfiguredError),
        ):
            resolve_dataset_roots(None)

    def test_raises_when_roots_is_only_commas(self) -> None:
        with (
            patch(
                "irsol_data_pipeline.prefect.variables.get_variable",
                return_value="",
            ),
            pytest.raises(DatasetRootNotConfiguredError),
        ):
            resolve_dataset_roots(("", "", ""))

    @pytest.mark.parametrize(
        "roots,expected",
        [
            (("/a",), [Path("/a")]),
            (("/a", "/b"), [Path("/a"), Path("/b")]),
            ((" /a ", " /b ", " /c "), [Path("/a"), Path("/b"), Path("/c")]),
        ],
    )
    def test_parametrized_parsing(
        self, roots: tuple[str, ...], expected: list[Path]
    ) -> None:
        result = resolve_dataset_roots(roots)

        assert result == expected
