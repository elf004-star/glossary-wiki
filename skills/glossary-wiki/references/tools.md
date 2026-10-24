# 工具与身份

## 依赖

首次运行检查 `hashdeep -h`、`ftag --help` 和 `uv --version`。缺失时说明安装方式：macOS 可用 `brew install hashdeep`；ftag 用 `cargo install ftag`。以本机帮助为准核对版本。工具未就绪时可以盘点与建立候选词，但标记增量/定位能力未验证，保持既有基线。

Python 一律通过 `uv run --python 3.11` 运行。辅助脚本仅依赖标准库和 Hashdeep；知识理解、术语访谈、汇总与 lint 由 agent 按本技能执行。

## Hashdeep 增量

创建 `state/scope.json` 后，在任意工作目录运行（用实际绝对路径替换变量）：

```sh
uv run --python 3.11 "$SKILL_ROOT/scripts/changes.py" scan "$TARGET_ROOT"
# 完成 pending.json 中全部变化的摄取与校验后：
uv run --python 3.11 "$SKILL_ROOT/scripts/changes.py" commit "$TARGET_ROOT" --reviewed
```

scan 调用 Hashdeep SHA-256，生成 pending 并输出 added/changed/removed；不推进基线。commit 重新校验内容与范围未变化才提交 manifest，并导出 sources.hashdeep。`--reviewed` 是 agent 对已完成语义工作的声明，脚本本身不能判断是否真的读过文档。它不会生成 wiki 页面。

脚本逐文件调用 Hashdeep，以避免逗号、Unicode 文件名和内容相同但路径不同导致错误匹配；大型仓库按子 wiki 分批，进程开销是已知限制。所有选中文件都需要读取字节计算哈希；节省的是 agent 的重复正文解析。原生 audit 可辅助诊断，但其内容匹配与 Unicode 路径限制不应取代逐路径 delta。

`manifest.json` 是上一次成功摄取的内容快照，导出的 `.hashdeep` 是可重建视图。新 scan 会替换 pending，所以先把未完成进度写入 coverage。仅扫描过但未提交的资料，下次仍会被报告。运行中断遗留 changes.lock 时，确认记录的进程已经退出后才移除锁。全局同步失败单独记待同步；不要为了消除差异伪造成功基线。

## ftag 与位置恢复

首次创建生成 UUID 作为 wiki_id，写入 wiki.json。在目标目录 `.ftag` 的第一个 `[path]` 段之前合并目录标签，保留用户原有内容：

```ini
[tags]
glossary-wiki gw-<wiki_uuid>
```

标签跟随目录；wiki ID 不依赖文件名。对每个已配置 search_root 执行：

```sh
ftag --path "$SEARCH_ROOT" query "gw-$WIKI_ID"
```

首次记录后用 ftag query/whatis 核验返回的目录与 wiki.json 中 ID 一致。ftag 从指定根递归查找，并不是系统级实时定位服务；search_roots 越准确，查找越有效。保留路径缓存，只有失效时做定位。

- 恰好一个有效匹配：更新 registry、父子关系、所有登记入站链接、投影来源路径和全局 index。用新位置解析内部相对链接，检查移动造成的跨目录来源失效。
- 多个匹配：目录复制会复制同一个 ID，这是 duplicate-id 状态。比较内容并让用户决定哪个是原身份；独立副本分配新 wiki_id，独立项目还需新 project_id 和对应概念 ID 映射，保留 derived_from。确认前不任选一个覆盖。
- 零匹配：记录搜索范围、离线卷/权限错误，标 missing。用户给出新位置则验证并扩展搜索根；未查全或没有删除证据时保留登记。

如果整棵项目树移动，逐个修复后代登记路径；使用 wiki ID 识别同一实体，再根据实际归属调整父级。移动到另一个项目须重新检查该项目术语唯一性。确认删除按 catalog.md 传播。

工具依据：[Hashdeep 手册](https://github.com/jessek/hashdeep/blob/master/man/hashdeep.1)、[ftag 官方说明](https://github.com/ranjeethmahankali/ftag)。
