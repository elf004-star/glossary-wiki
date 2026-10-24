# glossary-wiki

一个独立的 agent skill：先用文档驱动访谈统一术语，再把资料逐层编译为 `.Glossary-Wiki/`，支持增量摄取、本地优先的跨项目问答和健康检查。

结合 Karpathy 的持久 wiki 与 Matt Pocock 的术语建模、文档访谈、渐进披露理念。运行时不调用或依赖他们的技能。可安装包位于 [skills/glossary-wiki](skills/glossary-wiki/SKILL.md)。

## 全局安装

推荐复制整个 `skills/glossary-wiki/` 到 agent 的用户级 skills 目录，使任意项目都能使用。以 Codex 常用目录为例，首次安装：

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/glossary-wiki "${CODEX_HOME:-$HOME/.codex}/skills/glossary-wiki"
```

仅在目标目录尚不存在时执行上述复制。升级已有安装时备份并保留安装目录内 `catalog/` 的个人知识数据，只更新 SKILL.md、agents、references、scripts 和 ATTRIBUTION.md；不要用删除式同步覆盖整个目录。可在宿主的技能列表中确认已发现 glossary-wiki。

依赖：`uv`、`hashdeep`、`ftag`。macOS 可执行 `brew install hashdeep`，ftag 执行 `cargo install ftag`。技能内有工具检查和缺失处理；安装技能文件本身不会安装系统工具。

## 使用

```text
/glossary-wiki ingest
/glossary-wiki ingest /path/to/documents
/glossary-wiki 这个项目如何定义订单撤销？
/glossary-wiki lint
/glossary-wiki lint 全局 详细
```

宿主若使用 `$glossary-wiki`，将上面的技能调用前缀替换即可。技能是 agent 工作流，不是名为 glossary-wiki 的 shell 可执行程序。

项目数据保留在各自 `.Glossary-Wiki/`；总 index、总术语表和位置登记首次使用时写入技能目录的 `catalog/`。父级收录全部后代术语的可重建投影，知识正文仍在原 wiki。项目内术语唯一，全局同名异义按项目标注。默认快速 lint 只重新解析变化原文；详细 lint 全面复核。

Hashdeep 辅助脚本提供 scan/commit 两阶段基线；ftag 的目录内标签支持移动后重新发现。目录离开配置搜索范围、离线或不可读时显示待定位，不推断为删除。分类默认阈值、来源与字段格式详见技能内引用文档。

## 验证

```sh
uv run --python 3.11 -m unittest discover -s tests -v
```

测试覆盖脚本的内容变化、文件删除、未提交恢复、中文路径、子 wiki 边界和提交前变化。真实工具集成测试在找到 hashdeep 时执行，否则明确跳过。
