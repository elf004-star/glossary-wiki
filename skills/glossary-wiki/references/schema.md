# 数据约定

## 本地布局与所有权

```text
目标目录/
  .ftag
  .Glossary-Wiki/
    AGENTS.md
    index.md
    GLOSSARY.md
    pages/
    log.md
    state/
      wiki.json
      scope.json
      manifest.json
      pending.json
      sources.hashdeep
      dependencies.json
      coverage.md
```

`AGENTS.md` 是本 wiki 的架构文档：写覆盖边界、目录用途、命名与链接规则、术语权威位置、摄取/查询/lint 操作约定、分类阈值、子 wiki 与全局目录位置。它描述 wiki 架构；项目业务架构写入 pages。创建时填入实际值，不复制整份技能。已有约定先合并，保留人工内容。

`index.md` 每项含页面链接、摘要、覆盖范围；子目录有 wiki 时仅链接其 index。`log.md` 追加带日期的操作、来源变化、术语决定、未完成事项。`coverage.md` 列已完成/待处理/排除/不可读目录和批次，避免把未读当作不存在。

`wiki.json` 示例（UUID 由创建时生成）：

```json
{"schema_version":1,"wiki_id":"UUID","project_id":"PROJECT_UUID","parent_wiki_id":null,"title":"项目名","status":"active"}
```

顶层首次建立时 project_id 等于 wiki_id。项目内子 wiki 继承 project_id。后来建立父 wiki 时重新判定项目边界：若属于同一项目，保留所有 wiki_id，统一 project_id，并完成跨子目录术语冲突检查。只是收集多个独立仓库的文件夹可以是聚合容器，每个仓库仍有自己的 project_id。Git 根可作线索，无 Git 时以用户指定的项目边界为准。

`scope.json` 给增量脚本使用：`{"include":["**/*.md","**/*.txt"],"exclude":["vendor/**" ]}`。范围来自实际资料类型；代码、PDF、图片等按需要加入。脚本自动跳过自身生成目录、嵌套 wiki 所属子树、符号链接及常见依赖目录。被跳过的符号链接或特殊文件在 coverage 中说明；必要时显式指定其真实目录。修改 scope 后重新盘点并报告因排除而退出范围的资料。

`dependencies.json` 是原文相对路径 → 依赖该原文的 wiki 页面路径列表；另维护子 wiki ID → 引用页面的映射。引用的摘录、定义和结论都必须能找到来源，支持源文件删除后的失效传播。子 wiki 的 GLOSSARY、index、状态及依赖输出也需记录摘要；其输出改变会触发父级汇总，但不触发父级重复摄取子级原文。

## 术语条目

GLOSSARY 只承载概念与语言约定，实施细节放到 pages。每条采用稳定显式锚点，避免重命名后链接失效：

```markdown
<a id="term-UUID"></a>
## 结算单
- 概念 ID：PROJECT_UUID/TERM_UUID
- 定义：一次结算周期内应收费用的汇总凭据。
- 边界：与记录单次交易的订单不同。
- 规范名：结算单
- 别名／避免：账单（本项目统一写为结算单）
- 状态：已确认
- 权威：WIKI_UUID；本条
- 依据：[规则说明](../docs/billing.md#结算)；或标明用户决定与日期
```

待确认的候选放 coverage 的未决区，尚不能作为已定口径生成正文。文档明确且无冲突的定义可以标“文档确定”；涉及命名取舍或相互矛盾的定义必须由用户解决。引用代码与口头约定矛盾时并列呈现证据。

投影条目保留概念 ID、规范名、定义、别名、状态，额外标记“生成投影”、权威 wiki ID、权威条目链接与权威内容摘要。修改从权威条目开始，重建投影。多个子 wiki 使用同一概念时选一个权威条目，其余引用该概念 ID。

唯一性检查使用 Unicode NFKC、首尾空白清理、连续空白折叠、大小写折叠后的术语键，比较规范名和所有别名；跨中英文同义词需语义核对。项目内同一键指向两个概念即阻断；使用更明确的规范名并清除有歧义的别名。仅加子目录标签不能豁免项目内冲突。

## 页面证据

每页包含结论、相关概念 ID、原始资料链接及章节/页码、已摄取摘要、事实/推断/未决状态。源定位使用相对路径；跨 wiki 用 wiki ID 加相对页路径记录逻辑身份，并生成可点击链接。绝对路径链接只是可修复的展示位置。
