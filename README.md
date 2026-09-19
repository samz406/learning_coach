# Learning Coach · 深度学习教练

**把“看过一篇文章”推进到“能独立解释、应用，并在之后再次做出来”。**这是一个可安装到 **Claude Code、Codex CLI / IDE** 的 Agent Skill，主要使用中文，也会跟随你的语言。它根据你的回答决定讲解、提示、追问或换题，并把进度保存在本地学习档案中。

第一版提供三个入口：**带材料学习、继续学习、检验与复测**。适合学习技术原理、阅读知识文章和训练论证；开放议题评价理由与证据，不要求你同意作者。没有独立网页、模型账号或后台服务；使用你已有宿主的模型与权限。本地脚本不额外调用模型或服务，教学对话仍按宿主账号规则计费。

## 30 秒看懂它怎样工作

你说：“带我学认知负荷，我想知道怎么改进产品页面，今天 15 分钟。”教练会：

1. 确认具体目标，检查一个关键前置概念；零基础时先给短讲解和范例。
2. 请你自己解释或完成一个任务，每轮只推进一个主要问题，等待你的回答。
3. 针对回答中的缺口给提示、追问或示例，允许你随时说“不知道”“直接讲解”“暂停”。
4. 换一道新情境题检验独立应用；记录是否用过提示，不把背出刚看过的答案算作掌握。
5. 保存下次继续的位置；你再次调用时按记录续学或复测。

设计依据是认知负荷理论与 ICAP；这些理论提供教学思路，**不代表此 Skill 的学习效果已经经过实验验证**。它也不会自动给你设置复习提醒。

## 安装

### 前提

- 已安装并登录支持 Agent Skills 的 Claude Code 或 Codex CLI / IDE。
- Git（用于克隆）；**Python 3.9+**（安装工具和可靠学习档案工具，仅用标准库，无需 pip / API Key）。
- 若只使用教学指令，可以手动复制 Skill；没有 Python 时使用 Markdown 档案，见后文。

### macOS / Linux / WSL

```bash
git clone https://github.com/samz406/learning_coach.git
cd learning_coach

# 安装到两个平台的当前用户目录，供多个项目使用
python3 scripts/install.py --platform all
```

只使用一个平台时，把最后一行的 `all` 换成 `claude` 或 `codex`。已有安装会被保护，不会被静默覆盖。安装后进入你的学习工作目录，再打开宿主会话。

### Windows PowerShell

```powershell
git clone https://github.com/samz406/learning_coach.git
cd learning_coach
py -3 scripts/install.py --platform all
```

如果使用 WSL，在 WSL 内按 Linux 步骤安装；Windows 原生与 WSL 的用户目录不是同一个。下文的 `python3` 在原生 Windows 可替换成 `py -3`。

### 安装到某个项目 / 其他平台

```bash
# 在现有项目中使用；将路径替换成自己的目录
python3 scripts/install.py --platform all --scope project --project-dir /absolute/path/to/study

# 先看安装位置，不写文件
python3 scripts/install.py --platform all --dry-run

# 其他支持 Agent Skills 的宿主：指定其文档要求的 skills 目录
python3 scripts/install.py --skills-dir /absolute/path/to/host/skills
```

| 平台 | 用户级目录 | 项目级目录 | 对话中显式调用 |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/learning-coach/` | `<项目>/.claude/skills/learning-coach/` | `/learning-coach 带我学习……` |
| Codex CLI / IDE | `~/.agents/skills/learning-coach/` | `<项目>/.agents/skills/learning-coach/` | `$learning-coach 带我学习……` |
| 其他 Agent Skills 宿主 | 以该宿主文档为准 | 以该宿主文档为准 | 以该宿主文档为准；未逐一实测 |

核心仅用标准 `name`、`description` 和 Markdown 指令；`agents/openai.yaml` 是可忽略的 Codex 展示元数据。请复制整个 `skills/learning-coach/` 目录，不能只复制 SKILL.md，否则引用的教学规则、模板和脚本会缺失。安装目录依据 [Claude Code 官方文档](https://code.claude.com/docs/en/skills) 与 [OpenAI 官方文档](https://learn.chatgpt.com/docs/build-skills) 核对。

**验证安装：**Claude Code 输入 `/learning-coach`；Codex 在 `/skills` 或 `$` 选择器中寻找 `learning-coach`。也可以说“用 learning-coach 带我学一个知识点”。若找不到，先核对安装输出路径下是否有 SKILL.md，确认项目目录正确，并重新打开会话加载。仅克隆仓库不会自动安装。

## 使用

以下内容输入到宿主对话框中，**不是终端 shell 命令**。Claude Code 用 `/learning-coach`；Codex 把开头换成 `$learning-coach`。

### 1. 第一次体验：仓库自带材料

用户级安装后，在克隆仓库目录启动宿主并输入：

```text
/learning-coach 带我学习 examples/cognitive-load.md。我有产品设计经验，今天 15 分钟，目标是能分析一个页面中哪些提示该保留。
```

**项目级安装到别处时：**在安装目标项目目录启动宿主，把上面的材料路径换成克隆仓库中 `examples/cognitive-load.md` 的绝对路径；示例材料不随 Skill 复制。不要切回没有安装该 Skill 的仓库目录启动。也可以直接在该项目提供自己的材料。

也可以上传 PDF 或给出本地文件路径：

```text
/learning-coach 带我学这份 PDF，我想能用自己的话解释核心原理，并举一个工作中的应用。
```

文件提取、联网、OCR 由宿主提供；无法读取的材料会请你补充可读片段。第一轮通常是一小段定位加一个问题，零基础时可能先给范例；不会一次把整套问题与答案全部倒出来。

### 2. 学习过程中随时调整

```text
我不知道，先给我一个完整例子。
给一点提示，先别告诉我答案。
这部分我会了，直接用新场景考我。
直接讲解这道题。
今天到这里，保存进度。
```

### 3. 继续与复测

在相同工作目录、或明确指定同一档案根目录后输入：

```text
/learning-coach 继续上次认知负荷的学习。
/learning-coach 检验我是否还会用认知负荷分析页面，先别提示。
/learning-coach 从 /absolute/path/to/study/.learning-coach 继续认知负荷主题。
```

复测先作答再反馈，不先展示上次答案。找不到记录时会说明缺失；多个主题不明确时会请你选择。没有历史证据的第一次测验只能算当前诊断。

## 进度保存在哪里？能换平台吗？

默认保存在**启动学习时的工作目录**中的 `.learning-coach/<主题ID>/`。每次保存新增一个编号 JSON 快照，不覆盖旧作答；脚本校验证据引用、帮助程度和版本冲突。它记录学习目标、材料出处、用户回答、具体误区、已给的帮助、待答题、下次任务与建议复测日期。

Claude Code 和 Codex 在**同一目录**工作即可读取同一档案；换目录或换电脑时，需要指定/复制整个档案根目录。用户级安装只共享教学方法，不自动共享所有目录的学习记录。请勿同时在两个会话推进同一主题；版本检查会拒绝过期写入，教练重读合并后才能继续。

本仓库已忽略 `.learning-coach/`。在别的 Git 项目学习时，也请把 `.learning-coach/` 加入该项目 `.gitignore`，或使用仓库外的档案目录。工具默认不上传、不提交档案；**聊天中的学习内容仍会发给宿主模型，并不等于离线运行。**复测日期只是一条计划，不会自动触发通知。

- **没有 Python，但能读写文件：**教练使用 [便携 Markdown 模板](skills/learning-coach/assets/learning-record.md)，没有自动版本冲突保护。
- **没有文件权限：**继续对话教学，结束给出可复制记录；下次需要手动提供，不会声称已保存。
- **希望删除/备份：**备份或删除选定主题的整个目录；卸载 Skill 不会删除学习档案。

高级用户可直接查看记录（在仓库根目录执行；root 替换成实际位置）：

```bash
python3 skills/learning-coach/scripts/state.py --root .learning-coach list
python3 skills/learning-coach/scripts/state.py --root .learning-coach read --topic cognitive-load
```

完整数据协议、错误恢复和命令见 [档案协议](skills/learning-coach/references/state-protocol.md)。

## 更新与卸载

在克隆的仓库中更新，再重新安装：

```bash
git pull --ff-only
python3 scripts/install.py --platform all --replace
```

安装器在宿主配置目录下的 `learning-coach-backups/` 保存旧版本，再替换 Skill；不会改学习档案。项目级更新仍需带上原来的 `--scope project --project-dir ...`。`all` 的两处安装逐个执行，不是跨目录事务；某一处因权限失败时，修复权限后单独重试失败的平台。

卸载时删除对应平台的 `skills/learning-coach/` 文件夹即可；可按需删除备份。不要删除仍需保留的 `.learning-coach/` 档案。

## 验收与开发

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_package.py
```

测试覆盖安装位置、重复安装保护、备份更新、独立档案读取、历史不可改、过期版本冲突、帮助记录和无证据的掌握标签拒绝。实际教学行为的场景、结果和未验证项见 [验收记录](docs/acceptance.md)。

**支持边界：**已按官方格式实现 Claude Code / Codex 安装目录，并通过本地安装和脚本测试；本次环境没有这两个 CLI，尚未完成它们各自真实会话的加载验收。教学场景的独立代理检查不等同于 Claude 模型或 Codex CLI 端到端实测。第一版也不承诺统一所有模型的教学质量、自动调度、OCR 或科学验证的掌握度评分。

## 仓库结构

| 路径 | 用途 |
| --- | --- |
| `skills/learning-coach/SKILL.md` | 通用教学入口和行为约定 |
| `skills/learning-coach/references/` | 按需加载的教学规则、档案协议 |
| `skills/learning-coach/scripts/state.py` | 本地版本化学习档案工具 |
| `skills/learning-coach/assets/learning-record.md` | 无 Python 时的便携模板 |
| `skills/learning-coach/agents/openai.yaml` | Codex 展示元数据 |
| `scripts/install.py` | 跨平台复制安装与备份更新 |
| `examples/cognitive-load.md` | 首次体验的原创短材料 |
| `tests/`、`docs/acceptance.md` | 可运行测试和质量验收说明 |

教学规则的研究来源与适用边界见 [教学与证据规则](skills/learning-coach/references/teaching.md)。
