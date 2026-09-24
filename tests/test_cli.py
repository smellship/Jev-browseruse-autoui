"""CLI 子命令的离线单测：参数解析、退出码与打印（runner 用替身，不跑浏览器）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ui_agent import cli
from ui_agent.cli import main, parse_vars
from ui_agent.schema.plan import PlanStep
from ui_agent.schema.plan import TestPlan as Plan


def stub_result(run_dir: Path, steps=2) -> SimpleNamespace:
    return SimpleNamespace(status="ok", success=True, label="成功：全部断言通过", detail="全部断言通过",
                           steps=steps, checks=[], defect_candidates=["第1步 决策#0 CLICK: L4 降级"],
                           zoom_note="", report=run_dir / "report.html", run_dir=run_dir)


def fake_step(index: int = 1) -> SimpleNamespace:
    return SimpleNamespace(index=index, success=True, label="成功：全部断言通过", detail="全部断言通过")


def test_parse_vars_accepts_values_with_equals_and_rejects_junk():
    assert parse_vars(["账号=sysadmin", "令牌=a=b=c"]) == {"账号": "sysadmin", "令牌": "a=b=c"}
    assert parse_vars([]) == {}
    with pytest.raises(RuntimeError, match="key=value"):
        parse_vars(["没有等号"])
    with pytest.raises(RuntimeError, match="键名不能为空"):
        parse_vars(["=值"])


def test_no_supervisor_flag_turns_the_seam_off():
    from ui_agent.config import Settings

    on = cli.apply_overrides(Settings(ui_agent_supervisor=True), SimpleNamespace(no_supervisor=True))
    off = cli.apply_overrides(Settings(ui_agent_supervisor=True), SimpleNamespace(no_supervisor=False))
    assert on.ui_agent_supervisor is False and off.ui_agent_supervisor is True
    assert cli.apply_overrides(Settings(), SimpleNamespace(no_supervisor=False)).ui_agent_supervisor is True


def test_run_goal_mode_passes_vars_and_prints_tail(tmp_path, monkeypatch, capsys):
    seen: dict = {}

    class StubRunner:
        def __init__(self, settings, goal, url, checks=None, task="task", vars=None):
            seen.update({"goal": goal, "url": url, "checks": checks, "vars": vars, "task": task})

        def run(self):
            return stub_result(tmp_path)

    monkeypatch.setattr(cli, "Runner", StubRunner)
    code = main(["run", "--goal", "登录并查询", "--url", "http://x/", "--task", "baiwang",
                 "--check", "text_contains=票据类型", "--var", "账号=sysadmin"])

    assert code == 0
    assert seen["goal"] == "登录并查询" and seen["task"] == "baiwang"
    assert seen["vars"] == {"账号": "sysadmin"} and [c.kind for c in seen["checks"]] == ["text_contains"]
    out = capsys.readouterr().out
    assert "成功：全部断言通过" in out and "⚠ 第1步" in out and "报告：" in out


def test_run_returns_one_when_not_success(tmp_path, monkeypatch):
    class StubRunner:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            result = stub_result(tmp_path)
            result.success, result.status = False, "blocked"
            result.label = "阻塞：决策模型认为无法推进"
            return result

    monkeypatch.setattr(cli, "Runner", StubRunner)
    assert main(["run", "--goal", "x", "--url", "http://x/"]) == 1


def test_run_goal_mode_requires_url():
    with pytest.raises(SystemExit):
        main(["run", "--goal", "x"])


def test_run_plan_mode(tmp_path, monkeypatch, capsys):
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(Plan(name="登录", url="http://x/",
                              steps=[PlanStep(goal="登录"), PlanStep(goal="查询")]).model_dump_json(),
                         encoding="utf-8")
    seen: dict = {}

    class StubPlanRunner:
        def __init__(self, settings, plan, vars=None):
            seen.update({"plan": plan, "vars": vars})

        def run(self):
            return stub_result(tmp_path, steps=[fake_step(1), fake_step(2)])

    monkeypatch.setattr(cli, "PlanRunner", StubPlanRunner)
    code = main(["run", "--plan-file", str(plan_file), "--var", "密码=pw"])

    out = capsys.readouterr().out
    assert code == 0 and seen["vars"] == {"密码": "pw"}
    assert [s.goal for s in seen["plan"].steps] == ["登录", "查询"]
    assert "  01. ✓ 成功：全部断言通过" in out and "  02. ✓" in out


def test_run_plan_mode_accepts_url_override(tmp_path, monkeypatch):
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(Plan(name="登录", steps=[PlanStep(goal="登录")]).model_dump_json(), encoding="utf-8")
    seen: dict = {}

    class StubPlanRunner:
        def __init__(self, settings, plan, vars=None):
            seen["url"] = plan.url

        def run(self):
            return stub_result(tmp_path, steps=[fake_step()])

    monkeypatch.setattr(cli, "PlanRunner", StubPlanRunner)
    assert main(["run", "--plan-file", str(plan_file), "--url", "http://y/"]) == 0
    assert seen["url"] == "http://y/"


def test_plan_mode_without_any_url_is_rejected(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(Plan(name="登录", steps=[PlanStep(goal="登录")]).model_dump_json(), encoding="utf-8")
    assert main(["run", "--plan-file", str(plan_file)]) == 2
    assert "请用 --url 指定入口" in capsys.readouterr().err


def test_plan_command_writes_json(tmp_path, monkeypatch, capsys):
    def fake_make_plan(settings, description, url=""):
        return Plan(name="登录并查询", url=url, steps=[PlanStep(goal="登录")]), {"model": "stub", "latency_ms": 9}

    monkeypatch.setattr(cli, "make_plan", fake_make_plan)
    out = tmp_path / "plan.json"
    code = main(["plan", "--desc", "打开系统登录后查询发票", "--url", "http://x/", "--out", str(out)])

    assert code == 0 and out.exists()
    assert "计划「登录并查询」共 1 步" in capsys.readouterr().out


def test_report_command(tmp_path, capsys):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "result.json").write_text('{"status": "ok", "detail": "全部断言通过", "checks": []}',
                                         encoding="utf-8")
    (run_dir / "trace.jsonl").write_text("", encoding="utf-8")
    assert main(["report", "--run-dir", str(run_dir)]) == 0
    assert (run_dir / "report.html").exists() and "报告已生成" in capsys.readouterr().out
