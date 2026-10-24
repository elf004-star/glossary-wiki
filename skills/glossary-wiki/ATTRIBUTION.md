# 来源与独立性

本技能将下列理念重新组织成独立工作流，不需要安装或调用来源技能：

- Andrej Karpathy，LLM Wiki：原始资料、持久 wiki、架构约定三层；ingest/query/lint；内容 index 与时间 log。参考本仓库 `karpathy-llm-wiki/llm-wiki.md`、`llm-wiki-simple.md`。使用理念概述，不随安装包复制原文；当前本地材料未附明确许可，不将其声明为本包拥有的内容。
- Matt Pocock，writing-for-agents：上下文指针、渐进披露、步骤完成条件、单一事实来源。
- Matt Pocock，domain-modeling / GLOSSARY-FORMAT：规范语言、边界反例、发现冲突立即澄清、纯概念术语表。
- Matt Pocock，grilling 与 grill-with-docs：依赖有序的访谈和边讨论边记录。这里把流程内化，替换原版的技能调用；没有继承子代理派发或固定全局审批流程。

Matt Pocock 来源为 https://github.com/mattpocock/skills ，本仓库保留参考快照；相关改编附 [原 MIT 许可](references/MATTPOCOCK-LICENSE.txt)。

分层聚合、项目内术语强唯一、全局异义标记、Hashdeep 两阶段基线、ftag 身份与移动恢复、分类阈值属于此技能针对用户需求的设计。

工具文档仅用作 CLI 行为依据，不嵌入工具代码：
- https://github.com/jessek/hashdeep/blob/master/man/hashdeep.1
- https://github.com/ranjeethmahankali/ftag
