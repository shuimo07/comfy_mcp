# local-env — 把本机 WorkBuddy 数据钉在 E 盘

这个目录是本仓库的「本机环境治理」部分：让 Windows 上那些**路径写死在 C 盘**的程序
（WorkBuddy / CodeBuddy / pip / npm）把真实数据落到 E 盘，同时**不改任何配置里的路径**。

做法是 NTFS 目录联接（junction）：C 盘保留原路径，但它只是一个 0 字节重解析点，
读写全部落到 E 盘。**路径没变，所以调用方不需要改任何配置** —— 这正是「搬了存储还要改路径」
这件事在这里**不存在**的原因。

## 目录与它所在的联接

| | 路径 |
|---|---|
| 本目录（仓库内，唯一真源） | `E:\ComfyUI-MCP\local-env\` |
| 运行时的对外路径 | `E:\WBData\_tools\` → **junction** → 本目录 |

`E:\WBData\_tools` 故意保留成一个联接，因为启动项里的
`WorkBuddy-E-Guard.bat` 和 `guard.ps1` 内部都按这个绝对路径调用。
换机重建时：

```bat
:: 假定仓库已 clone 到 E:\ComfyUI-MCP
mklink /J E:\WBData\_tools E:\ComfyUI-MCP\local-env
```

## 现行脚本

| 文件 | 用途 |
|---|---|
| `guard.ps1` | 登录自愈入口：遍历映射表 + 压制 WorkBuddy 开机自启 |
| `guard-core.ps1` | `Ensure-Junction` 实现（复制 → 校验 → 查进程 → 删源 → 挂联接） |
| `audit_links.py` | **只读**审计：列出每个映射当前是联接还是真实目录 |
| `fix_workspace_junction.py` | 修复断掉的工作区联接（安全校验后删空壳 + 重建） |
| `fix_ps1_bom.py` | 给 `.ps1` 补 BOM + CRLF（**改完任何 PowerShell 脚本必跑**） |
| `修复工作区联接.bat` | 上面那个 py 的双击入口（需先完全退出 WorkBuddy） |
| `FinishMoveToE.bat` | 检查 WorkBuddy 已退出 → 跑 `guard.ps1` → 逐项验证 |
| `使用说明.md` | **详细运维文档**（映射表、踩坑、安全约束），以它为准 |

`legacy/` 放已被 `guard.ps1` 取代的早期搬迁脚本（`migrate*.ps1`、`relocate.py`、
`scan_links.py`、`finish-to-E.ps1`）与历史日志，仅作存档。

## 完整路径映射

见 `使用说明.md` 的映射表。要点：

- **`guard.ps1` 是幂等的**，重复运行不会做多余的事；它还会把
  `settings.json` 的 `autoLaunchDesired` 改回 `false`、删掉注册表 Run 里的自启值 ——
  所以用户不需要手动关自启。
- **junction 会被周期性破坏**（实测 19:03 还是联接、00:15 已变回真实目录）。
  所以守卫挂在登录启动项不是冗余，是命脉；长期不注销/重启就会漏。
- **`.workbuddy`（约 24 万文件 / 2.4 GB）是最后一块**，因为 WorkBuddy 运行时
  自身就跑在它上面（cwd 句柄锁），只能交给**下次登录**整体搬迁。

## 改脚本后的自检

```bat
python E:\WBData\_tools\fix_ps1_bom.py
```

```powershell
$e=$null;$t=$null
[System.Management.Automation.Language.Parser]::ParseFile('E:\WBData\_tools\guard.ps1',[ref]$t,[ref]$e)
$e.Count   # 必须是 0
```

**PowerShell 5.1 会把「无 BOM 的 UTF-8」当 GBK 读**，`.ps1` 里只要有中文注释就会解成乱码、
报语法错误且行号是错的 —— 本守卫曾因此静默失效过。所以改完必须补 BOM。

## 相关技能

方法论已整理成技能 `windows-autostart-and-junction-audit`，副本在
本仓库 `skills/windows-autostart-and-junction-audit/SKILL.md`。
