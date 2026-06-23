"""Pilot tests for the Build exFAT view (run_build mocked — no real build)."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from textual.widgets import ContentSwitcher, Input, Label, Select, Static, Switch

import mkpfs_tui.screens.build_exfat as build_screen
from mkpfs_tui.app import MkpfsTuiApp
from mkpfs_tui.deploy.deployer import DeployResult
from mkpfs_tui.exfat.builder import BuildResult
from mkpfs_tui.screens.build_exfat import BuildExfatView
from mkpfs_tui.widgets.path_field import PathField
from mkpfs_tui.widgets.result_panel import ResultPanel

_PARAM = {
    "titleId": "PPSA01234",
    "contentVersion": "01.00",
    "localizedParameters": {"defaultLanguage": "en-US", "en-US": {"titleName": "My Game"}},
}


def _dump(tmp_path: Path) -> Path:
    dump = tmp_path / "DUMP"
    (dump / "sce_sys").mkdir(parents=True)
    (dump / "sce_sys" / "param.json").write_text(json.dumps(_PARAM))
    (dump / "eboot.bin").write_bytes(b"\0" * (2 * 1024 * 1024))
    return dump


async def test_autofills_output_label_and_estimate(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    app = MkpfsTuiApp()
    async with app.run_test() as pilot:
        app.query_one("#work", ContentSwitcher).current = "build"
        await pilot.pause()
        view = app.query_one("#build", BuildExfatView)
        view.query_one("#build-source", PathField).value = str(dump)
        await pilot.pause()
        assert view.query_one("#build-output", PathField).value.endswith("PPSA01234 - My Game (01.00).exfat")
        assert view.query_one("#build-label", Input).value == "PPSA01234"
        assert "MB" in str(view.query_one("#build-estimate", Static).content)


async def test_build_button_shows_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dump = _dump(tmp_path)
    out = tmp_path / "o.exfat"
    monkeypatch.setattr("mkpfs_tui.screens.build_exfat.preflight", lambda *, verify: [])
    monkeypatch.setattr(
        "mkpfs_tui.screens.build_exfat.run_build",
        lambda opts: BuildResult(True, str(out), 128, 65536, "PPSA01234", ()),
    )
    app = MkpfsTuiApp()
    async with app.run_test(size=(120, 40)) as pilot:
        monkeypatch.setattr(app, "suspend", lambda: contextlib.nullcontext())
        app.query_one("#work", ContentSwitcher).current = "build"
        await pilot.pause()
        view = app.query_one("#build", BuildExfatView)
        view.query_one("#build-source", PathField).value = str(dump)
        view.query_one("#build-output", PathField).value = str(out)
        await pilot.pause()
        await pilot.click("#build-run")
        await pilot.pause()
        notes = [str(label.content) for label in view.query_one("#build-result", ResultPanel).query(Label)]
        assert any("Built" in note for note in notes)


async def test_preset_switch_changes_output(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    app = MkpfsTuiApp()
    async with app.run_test() as pilot:
        app.query_one("#work", ContentSwitcher).current = "build"
        await pilot.pause()
        view = app.query_one("#build", BuildExfatView)
        view.query_one("#build-source", PathField).value = str(dump)
        await pilot.pause()
        view.query_one("#build-preset", Select).value = "ppsa"
        await pilot.pause()
        assert view.query_one("#build-output", PathField).value.endswith("PPSA01234.exfat")


async def test_deploy_after_build_runs_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dump = _dump(tmp_path)
    out = tmp_path / "o.exfat"
    monkeypatch.setattr(build_screen, "preflight", lambda *, verify: [])
    monkeypatch.setattr(
        build_screen, "run_build", lambda opts: BuildResult(True, str(out), 128, 65536, "PPSA01234", ())
    )
    deployed: dict[str, object] = {}

    def fake_run_deploy(opts: build_screen.DeployOptions, **kw: object) -> DeployResult:
        deployed["file"] = opts.local_file
        return DeployResult(True, "/p/o.exfat", 99)

    monkeypatch.setattr(build_screen, "run_deploy", fake_run_deploy)
    app = MkpfsTuiApp()
    async with app.run_test(size=(120, 40)) as pilot:
        monkeypatch.setattr(app, "suspend", lambda: contextlib.nullcontext())
        app.query_one("#work", ContentSwitcher).current = "build"
        await pilot.pause()
        view = app.query_one("#build", BuildExfatView)
        view.query_one("#build-source", PathField).value = str(dump)
        view.query_one("#build-output", PathField).value = str(out)
        view.query_one("#build-host", Input).value = "1.2.3.4"
        view.query_one("#build-deploy-after", Switch).value = True
        await pilot.pause()
        await pilot.click("#build-run")
        await pilot.pause()
        assert str(deployed.get("file")) == str(out)
