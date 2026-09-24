# ui_agent

自然语言驱动的 UI 测试执行器：**LLM 编排与裁决，TypeSafe Jev 决策，Playwright 执行。**

用户只给一句自然语言描述流程；LLM 把它拆成分步计划（每步一个小 goal + 独立断言），
常态循环里由 Jev 看 DOM 快照选"操作 + 目标元素"，只有 Jev 卡住时才由 LLM 介入裁决
（HINT / RECOVER / REPLAN / ABORT）。

## 快速开始

```powershell
cd D:\test_skills\ui_agent
uv sync

# 浏览器装到工作区内置目录（首次）
. .\scripts\env.ps1
uv run playwright install chromium

# 无网络冒烟：验证双模式启动与 DOM 读取
uv run python scripts\smoke_browser.py            # 无头
uv run python scripts\smoke_browser.py headed     # 可视化（会弹窗几秒）

# 离线全链路冒烟：本地夹具跑 快照 → 守卫 → 点击阶梯 → 断言（零模型调用）
uv run python scripts\smoke_snapshot.py
uv run python scripts\smoke_snapshot.py --headed  # 可视化看它怎么点

# 离线多步冒烟：脚本化决策跑一条两步计划（一个会话、零模型调用）
uv run python scripts\smoke_plan.py
uv run python scripts\smoke_plan.py --headed

# 离线监督冒烟：脚本化监督模型跑三条升级路径（HINT / RECOVER / ABORT，零模型调用）
uv run python scripts\smoke_supervisor.py
uv run python scripts\smoke_supervisor.py --headed

# 离线上传冒烟：A（隐藏 input 注入 U1）与 C（页内合成拖拽 U2）两条通道 + 一条页面拒收负例
uv run python scripts\smoke_upload.py
uv run python scripts\smoke_upload.py --headed          # 可视化看拖拽与提交
uv run python scripts\smoke_upload.py --files a.png b.pdf   # 指定上传文件（默认复用已有截图）
```

## 跑一个目标

```powershell
# 只看不点：把即将喂给 Jev 的 state 打出来（零模型调用）
uv run ui-agent snapshot --url http://example.com

# 跑目标：debug 模式可视化；断言用 --check 独立指定（DONE 不算证据）
uv run ui-agent run `
  --goal-file examples\goals\baiwang_login.txt `
  --url http://cs-electronic-bills-ng-http.default.hw-bw-prd-1.prd.baiwang.com `
  --task baiwang-login --mode debug `
  --var 账号=<账号> --var 密码=<密码> `
  --check element_exists=行政区域

# 回归（无头）：同一份代码、同一个 Chromium 二进制
uv run ui-agent run --goal-file examples\goals\baiwang_full.txt --url <网址> --mode ci `
  --check element_value=行政区域|2102 大连 `
  --check text_contains=票据类型
```

示例目标文件里**不含任何真实凭据**：账号、密码、上传文件路径一律在运行时用 `--var` 注入
（值不落盘、不进任何模型调用），所以这些文件可以安全地进版本库。

断言写法：`kind=值`、`element_value=标签|期望值`，或直接给 JSON。可用 kind：
`text_contains / url_contains / title_contains / element_exists / element_absent / element_value`。

## 跑一条计划（M1）

```powershell
# 1) 一段自然语言流程 → 分步计划（这一步会调用文本模型）
uv run ui-agent plan --desc "打开系统，用账号登录，行政区域选 2102 大连，点查询，看到票据列表" `
  --url <网址> --out plans\baiwang.json

# 2) 按计划执行：一个浏览器会话跑完所有步骤，每步独立断言，失败即停
uv run ui-agent run --plan-file plans\baiwang.json --mode debug

# 3) 重出报告（不需要重跑）
uv run ui-agent report --run-dir .artifacts\runs\<某次运行>
```

`--var 键=值` 可以给 `TYPE_TEXT` 字段直接供值（优先于文本模型，值不落盘、不进模型），
也可以给 `UPLOAD` 供**上传文件路径**（键名要出现在控件标签里，多文件用 `;` 分隔）；
适合口令等不便写进目标的场景；缺值且没有文本模型时，字段会被拒填并记为失败而不是猜一个值。

## 卡住了怎么办（M2）

常态循环不调 LLM；只有下面五种情况会停下来问一次监督模型（HINT / RECOVER / REPLAN / ABORT）：

| 触发点 | 什么时候 |
|---|---|
| `blocked` | Jev 说没有任何支持的操作能推进 |
| `repeat_no_progress` | 同一个决策连做 3 次且页面没有变化 |
| `low_confidence` | 连续 3 次决策置信度低于 `UI_AGENT_CONF_MIN` |
| `budget_actions` / `budget_decisions` | 动作或决策预算耗尽 |
| `check_failed` | 第一次 DONE 没通过断言（第二次直接判失败） |

裁决由代码裁决，不由模型自己保证：元素只能用当次快照里的 index，恢复动作只允许
`CLICK / SELECT / HOVER / SCROLL_TO / PRESS_KEY / SCROLL_UP / SCROLL_DOWN / WAIT`（不含 `CLICK_FORCE`
与 `TYPE_TEXT`），SELECT 的选项必须在该元素当次选项里且未禁用，REPLAN 的步骤要过与 planner 相同的断言检查。
RECOVER 的动作走和 Jev 决策完全相同的执行路径（守卫、降级阶梯、缺陷通报都照旧）。

预算：`SUPERVISOR_PER_STEP`（默认 2，每步重置）与 `SUPERVISOR_PER_RUN`（默认 6，整轮共享），
在调用前扣除，所以升级次数有限、循环必然终止。监督模型不可用（没 key、预算用完、回答不合规）
时行为与 M0 完全一致：直接停机。`--no-supervisor` 或 `UI_AGENT_SUPERVISOR=false` 可以关掉这个缝。

计划模式下 REPLAN 会把**剩余步骤整体换成新序列**（原计划留在 `plan.json`，新计划写 `plan.final.json`，
重试的那一步另开 `-r2` 目录，`summary.json` 里有 `replans` 记录）；单目标模式下 REPLAN 只会停在
`replanned` 状态并提示改用计划模式——不会假装成功。

## 上传文件（拖拽 / 点选）

`UPLOAD` 操作的目标只能是**文件控件**（role `file`，快照里带 `accept` / `multiple` 事实）；
被 `display:none` 藏起来也算，因为真实用户入口就是那个按钮或拖拽框。走哪条通道由**配置**决定，
不由模型选，也不做跨通道静默回退：

| 通道 | 开关 | 阶梯级别 | 机制 |
|---|---|---|---|
| A：隐藏 input 注入 | `--upload-mode input`（默认）/ `UI_AGENT_UPLOAD_MODE=input` | `U1` | `set_input_files`，协议层设置 FileList |
| C：页内合成拖拽 | `--upload-mode drop` | `U2` | 页内造 `DataTransfer` + `dragenter/dragover/drop`（`isTrusted=false`，属已知限制） |

文件路径只来自 `--var`（键名要出现在控件标签里，多文件用 `;` 分隔），**没有模型兜底**：匹配不上就干净地拒绝
（"未执行上传"）而不是猜一个路径。执行前只做确定性预检（文件存在、扩展名/MIME 对得上 `accept`、单文件控件不给多个），
大小与数量上限属于**页面自己的策略**，用断言判（本地夹具与百望页面都把它们写在页面上）。

`UPLOAD` 常是两段式：先进入待提交列表，再点提交才算数——所以验收要看提交后的文案（如 `text_contains=提交成功`），
以及待提交列表里的**文件名**。产物里只落**文件名 + 大小 + 变量键名**（trace 的 `upload` 字段），本地绝对路径不落盘、不进模型。

本地夹具 `examples/local_fixture.html` 复刻了百望上传页的规则（pdf/jpg/jpeg/png、图片 ≤ 20M、PDF ≤ 10M、≤ 50 个），
`scripts/smoke_upload.py` 用真实 Chromium 跑 A、C 两条通道各一次，外加一条负例（往未声明 `accept` 的控件传 `.txt`，
页面必须自己拒收并给出文案），全程零模型调用。

## 产物

单目标运行在 `.artifacts/runs/<任务>-<时间>/` 留下：`result.json`、`trace.jsonl`（每步决策与降级级别）、
`actions.json`（动作 + 是否改变页面）、`snapshots/*.json`（喂给模型的 state）、`report.html`。

计划的运行目录多出：`plan.json`、`summary.json`（逐步结果 + `replans`）、`steps/<NN-目标>/`（每步自成一套产物）、
`report.html`（汇总报告，截图按相对路径引用）；发生重排时还有 `plan.final.json`。
截图只在 debug 模式逐步留存，ci 只留失败一张。

## 目录

| 路径 | 内容 |
|---|---|
| `src/ui_agent/cli.py` | 命令行：`plan` / `run` / `snapshot` / `report`（`run --no-supervisor` 可关掉监督缝） |
| `src/ui_agent/llm/` | 三个 LLM 缝：planner 编排、textfill 字段取值、supervisor 卡住裁决 |
| `src/ui_agent/observe/` | state 组装；`js/snapshot.js` 页面内取数与索引标记；`js/guard.js` 执行前守卫 |
| `src/ui_agent/decide/` | Jev 客户端、questions 模板、提示词 |
| `src/ui_agent/driver/` | Playwright 驱动：双模式启动、点击降级阶梯、跨 frame 快照 |
| `src/ui_agent/act/` | 白名单动作执行 + 守卫预检 + 降级通报；上传取值校验（`upload.py`） |
| `src/ui_agent/verify/` | 独立断言（文本/URL/元素/控件值），不看模型自述 |
| `src/ui_agent/run/` | 单目标主循环与多步计划执行、卡住检测、监督升级、预算、产物落盘 |
| `src/ui_agent/schema/` | 契约：state / decision / check / plan / supervisor / status |
| `src/ui_agent/report/` | HTML 报告（计划模式读 `summary.json`，单目标读 `result.json`） |
| `tests/fakes.py` | 离线单测的假驱动、假决策引擎与脚本化监督模型（不起浏览器、不调模型） |
| `.browsers/` | 工作区内置浏览器（gitignore，`scripts/env.ps1` 导出路径） |
| `.artifacts/` | 持久化 profile、运行产物（gitignore） |
| `examples/goals/` | 现成的自然语言目标（百望登录、百望全流程） |

## 状态

M0 完成：单目标循环可跑（state → Jev → 执行 → 断言），零模型调用即可验证快照/守卫/降级阶梯。

M1 完成：planner 拆解 + 多步计划执行（一个会话、失败即停、历史交接）+ 独立断言 + HTML 报告 + `--var` 供值。

M2 完成：卡住/阻塞/预算/断言未过时交给监督模型（HINT / RECOVER / REPLAN / ABORT），
裁决与落点由代码校验，预算有限、不可用即退回 M0 停机语义；计划模式支持整体重排。

M3 部分完成：**上传**已可用（见上，A/C 两条通道 + 页面级验收），iframe / shadow DOM / 新标签 / 弹窗仍未开始。
M4（批量回归）未开始。

离线单测 180 项与四个冒烟脚本（`smoke_snapshot` / `smoke_plan` / `smoke_supervisor` / `smoke_upload`）全绿。

实跑校准（2026-09-23，百望非税查询页）：`goto` 之后**不能立刻信快照**——页面 `domcontentloaded`
后先渲染壳（约 20 个导航元素），内容区 0.8–3 秒后才到，中间那段窗口"看起来稳定"却没有任何
业务控件。所以：

- 首次渲染过一道就绪门（`ready_stable_ms`，默认 2.5s 指纹不动才算渲染完），导航后先等它；
- 快照里一个元素都没有时（SPA 偶发全空白）刷新一次再看，只刷一次，之后按事实交给决策层；
- 模型的传输层错误（DNS / 连接重置 / 超时）重试，HTTP 4xx/5xx 不重试。

`SCROLL_TO` 的可选性一度与目标 head 不一致（目标 head 从来没有被组装出来，模型一选就抛错），
现在两者都由 `build_action_space` 派生，不会再分叉。

实跑记录：登录 → 行政区域"2102 大连" → 查询 的完整流程与单独的查询流程都已可视化跑通
（Jev 逐步决策，脚本断言验收；凭证只经 `--var` 注入，产物里没有明文密码）。

模型密钥：文本模型接 **DeepSeek 官方**（`https://api.deepseek.com/v1`，`TEXT_MODEL=deepseek-flash`
即 V4.1-Flash）；`.env` 里已有 key。`TEXT_MODEL_REASONING=none` 关掉思考（实测掉出
`reasoning_content`，同题 5 tokens vs 40）；想让它思考就改成别的值。
密钥只进 `.env`（已 gitignore）：单测由 `tests/conftest.py` 钉成空串，冒烟脚本显式关监督缝，
两者都不会联网计费；脚本化的 `--var` 路径也不需要 key。

