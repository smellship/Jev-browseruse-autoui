"""集中配置：.env → Settings；浏览器目录固定在工作区内。"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BROWSERS_DIR = PROJECT_ROOT / ".browsers"
ARTIFACTS_DIR = PROJECT_ROOT / ".artifacts"

# Playwright 在启动子进程时读这个变量；在导入任何 playwright 之前固定到工作区
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_DIR))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    typesafe_api_key: str = ""
    typesafe_model: str = "jev-latest"
    typesafe_base_url: str = "https://api.typesafe.ai/v1/systemone"

    text_model_api_key: str = ""
    text_model_base_url: str = "https://api.deepseek.com/v1"
    text_model: str = "deepseek-flash"
    text_model_reasoning: str = "none"

    ui_agent_mode: str = "debug"
    ui_agent_viewport: str = "1920x1080"
    ui_agent_conf_min: float = 0.55
    ui_agent_supervisor: bool = True
    ui_agent_upload_mode: str = "input"  # input=给隐藏 input 注入文件；drop=页内合成拖拽事件

    max_actions: int = 60
    max_decisions: int = 120
    supervisor_per_step: int = 2
    supervisor_per_run: int = 6
    max_elements: int = 250
    max_text: int = 6000
    slow_mo: int = 250
    settle_ms: int = 700
    ready_stable_ms: int = 2500    # 首帧就绪门：指纹安静这么久才算渲染完成（壳先渲染、内容后到）
    ready_timeout_ms: int = 20000  # 就绪门的最长等待；超时按当前快照继续，不阻塞运行

    @property
    def headless(self) -> bool:
        return self.ui_agent_mode != "debug"

    @property
    def viewport(self) -> tuple[int, int]:
        w, h = self.ui_agent_viewport.lower().split("x")
        return int(w), int(h)

    @property
    def profile_dir(self) -> Path:
        return ARTIFACTS_DIR / "chrome-profile"

    @property
    def runs_dir(self) -> Path:
        return ARTIFACTS_DIR / "runs"
