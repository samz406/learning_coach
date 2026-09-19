# 学习档案协议

## 位置与发现

默认 root 是调用时工作目录下的 `.learning-coach/`。首次使用告知路径即可；用户指定其它根目录则使用它，并在后续调用保持一致。不要把资料放进 Skill 安装目录。不同工作目录不会自动共享进度；跨平台续学要指向同一个 root。没有文件权限时使用 SKILL.md 的降级方式，不尝试绕过宿主权限。

先用 `list` 查主题；明确主题用 `read`。主题 ID 使用 1–64 个小写字母、数字、连字符，标题可用中文。不要读取与学习请求无关的目录。多个候选不默选最新。保存实际成功后报告完成；工具错误不会变成学习结果。

以下 `<skill-dir>` 是当前加载的 SKILL.md 所在目录，`<root>` 是确定后的档案绝对路径。替换为真实值，使用宿主的文件工具或安全参数传递；不要把用户答案拼进 shell 命令。

```bash
python3 "<skill-dir>/scripts/state.py" --root "<root>" list
python3 "<skill-dir>/scripts/state.py" --root "<root>" init --topic cognitive-load --title "认知负荷" --goal "分析一个页面的必要指导与无关干扰"
python3 "<skill-dir>/scripts/state.py" --root "<root>" read --topic cognitive-load
python3 "<skill-dir>/scripts/state.py" --root "<root>" save --input "<draft-file>" --expected-revision 1
```

Windows 可用 `py -3` 替代 `python3`。仅在 Python 3.9+ 可用时运行脚本。工具不联网，也不调用模型。

## 保存流程

1. 初始化只做一次；重复 init 会拒绝覆盖。读取完整最新记录和 revision。
2. 在 root 内写一个临时 JSON 草稿：保留 topic_id、schema_version、历史 attempts；更新目标、阶段、概念、pending_task 等，追加真实回答。不要通过追加虚构回答通过验证。
3. 用读取到的 revision 保存。脚本验证数据并原子写入新版本；成功后移除临时草稿并回读一次核对关键字段。
4. 冲突时重读最新状态，理解两边的变化后合并；最多重试一次，仍冲突则保留草稿并告知，不不断覆盖。仅新的真实回答可以追加。被新状态取代的 pending_task 不应恢复。
5. 不自动删除 `.write.lock`。若进程崩溃留下锁，确认没有写入进程后再由用户处理；同时说明旧快照仍在。

每个主题采用 `root/<topic-id>/00000001.json`、`00000002.json` 等完整快照；读取最大版本。没有第二套可漂移的摘要文件。第一版以个人少量主题为目标，完整快照会随历史增大，可手动备份/归档整个主题目录；不声称适合无限数据。旧快照有错误时保留审计历史，追加纠正记录并调整当前判断。

## 字段

| 字段 | 含义 |
| --- | --- |
| schema_version | 固定为 1 |
| topic_id / title / goal | 稳定主题 ID、显示名、本次可验收目标 |
| revision / updated_at | 脚本生成的版本和 UTC 更新时间 |
| sources | 字符串列表，材料标题＋页码/章节/URL；无法读取则明确注明 |
| preferences | 已知偏好，如语言、时间预算；不推断敏感特征 |
| stage | orient、diagnose、explain、practice、challenge、transfer、review、paused、complete |
| concepts | id、name、label、evidence_ids、gap；规则见 teaching.md |
| attempts | 追加式真实作答历史，结构如下 |
| pending_task | 等待回答的题，或 null；包括已提供的帮助 |
| next_action | 清楚描述下次做什么及原因，非空字符串 |
| review_on | YYYY-MM-DD 或 null；建议日期，不是定时任务 |

attempt：`id`（唯一）、`concept_id`、`task_id`（同题重试保持相同）、`prompt`、`kind`（diagnose/explain/practice/transfer/review）、`answer`、`support`（none/hint/worked_example/answer）、`outcome`（pass/partial/fail）、`feedback`（判断依据）、`at`（ISO 8601，含时区）。如果错误评价需要纠正，追加新 attempt 并在 feedback 中注明原 ID，不改旧记录。评估不确定时保守记录 partial 并说明原因。

pending_task：`task_id`、`concept_id`、`prompt`、`kind`、`support`。发题就写入；提供提示后更新 support；得到回答后将原题与实际帮助程度写入 attempts，再换下一题或置 null。跨会话不能丢掉曾经给出的帮助。

脚本检查结构、证据关联和部分必要条件，不能检查答案真实性、是否偷偷改题或模型评价是否正确。不要把脚本通过当成学习质量通过。`retained` 的机械最低要求是前后成功证据位于不同 UTC 日期，教学上还要核实确实经过有意义的间隔；跨午夜几分钟不算可靠保持证据。

## 示例快照（虚构，仅说明结构）

```json
{
  "schema_version": 1,
  "topic_id": "cognitive-load",
  "title": "认知负荷",
  "goal": "区分必要指导与无关干扰",
  "sources": ["examples/cognitive-load.md：教学概述"],
  "preferences": {"language": "zh-CN", "minutes": 15},
  "stage": "challenge",
  "concepts": [{"id": "guidance", "name": "必要指导", "label": "exposed", "evidence_ids": ["a1"], "gap": "把删除所有提示当成简化"}],
  "attempts": [{"id": "a1", "concept_id": "guidance", "task_id": "t1", "prompt": "如何降低新手使用页面时的无关负担？", "kind": "diagnose", "answer": "把所有提示都删掉。", "support": "none", "outcome": "partial", "feedback": "注意到了界面精简，但没有区分必要指导与干扰。", "at": "2026-09-19T10:00:00+00:00"}],
  "pending_task": {"task_id": "t2", "concept_id": "guidance", "prompt": "第一次使用的人失去操作示例后，可能遇到什么问题？", "kind": "explain", "support": "hint"},
  "next_action": "等待用户回答 t2，检验能否区分必要指导与干扰。",
  "review_on": null
}
```
