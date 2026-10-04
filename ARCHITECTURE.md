# ARCHITECTURE.md — agent-relay 提示词工程解剖

> 本文从提示词工程视角解释 [SKILL.md](SKILL.md)。`agent-relay` 是纯指令型
> Agent Skill：不依赖专用脚本或运行时协议，只要求 Agent 能读取仓库并执行 Git。

## 一句话定位

`agent-relay` 把 Git 分支、ref range 或 working tree 的变化压缩成一份可核验的
五部分 Markdown 摘要，让人或后续 Agent 无需通读 diff，也能理解交付结果、精确规模、
核心变化、主要模块和开发过程。

它总结的是 Git 变化集，而不是一般性的产品能力、代码质量或发布说明。这个边界同时写在
frontmatter 中，避免“总结一下仓库”之类的近似请求误触发 branch-summary 模板。

## 输入输出契约

### 支持的输入

- 分支或两个任意 ref 的比较；
- 明确的 commit range；
- staged、unstaged、untracked 并存的 working tree；
- 用户明确要求时，已提交分支变化与本地 WIP 的组合摘要。

先选模式，再解析 ref：

| 模式 | 树比较 | 历史 |
| --- | --- | --- |
| `branch-introduced` | 唯一 merge-base → target | `base..target` 右侧独有提交 |
| `endpoint-snapshot`（含显式 `A..B` diff） | A → B | 可选 `A..B` 辅助历史，不代表完整树差异的来源 |
| 显式 `A...B` diff | 唯一 merge-base(A,B) → B | 右侧历史 `A..B`；归入 `branch-introduced` |
| `single-commit` | 唯一 parent → C；root 用 empty tree；merge 先问 parent | 只有 C，1 commit |
| `working-tree` | HEAD → index、index → worktree；另算 HEAD → worktree 净值 | 0 commit，untracked 单列 |

`git log A...B` 是两侧提交的对称差，与三点 diff 不同。用户若要这个提交集合，需用
`--left-right` 标明两侧，不能冒充 target 开发时间线。范围意图含糊时先问，不擅改点号。

目标 ref 优先使用用户指定值，否则使用 `HEAD`。仅需要发现基线的分支摘要按以下顺序解析，
显式端点和单 commit 不走默认分支回退：

1. 用户明确指定的 baseline；
2. `origin/HEAD` 指向的仓库默认分支；
3. `origin/main`、`origin/master`、`main`、`master`。

用户给出的 ref 无效时不会静默回退。ref 校验后会解析为完整 commit ID，后续
`merge-base`、`rev-list`、`log` 和 `diff` 都使用不可变 SHA，避免取证期间分支移动导致
报告内部范围不一致。

### Git 事实层

按模式固定 left/right 树端点，文件数、行数、模块统计和 patch 共用这对端点；历史另行标注：

| 事实 | 命令 | 用途 |
| --- | --- | --- |
| 分支右侧 commit 数 | `git rev-list --count <base>..<target>` | 历史规模，不是树差异数量 |
| 分支时间线 | `git log --reverse ... <base>..<target>` | 开发演进 |
| 路径状态 | `git diff --name-status -z --find-renames <left> <right>` | 新增、修改、删除、重命名 |
| 行数 | `git diff --numstat -z --find-renames <left> <right>` | 精确的文本增删量和二进制识别 |

`git merge-base --all` 只有一个结果时才用于分支归因；零个结果不暗转 snapshot，多个结果
不任取一个，应说明边界并请用户选择端点。浅历史或缺失对象不能证明真实无祖先。
单提交用 `git rev-list --parents -n 1` 查 parent，root 的 empty-tree ID 用仓库自身对象
格式动态生成，不硬编码 SHA-1；merge 不使用可能省略变化的默认 combined diff。
端点比较的右侧独有提交只能称辅助历史，baseline 侧变化也可能影响树差异。
空 diff 和空历史分别判断，例如 revert 可使净变化为零而历史非空。

数字只是索引，不足以证明行为。Skill 还要求阅读实际 patch，以及有代表性的实现、测试和
文档。commit subject 只负责解释时间线，不能单独作为“功能已实现”的证据。

生成代码、protobuf、vendor、lockfile 和二进制会扭曲规模感知，因此需要单独标注。rename
检测后按一个路径统计；二进制计入文件数但不编造行数；submodule 只描述可观察到的指针变化。

### Working tree 事实层

未提交修改分为三个互不替代的来源：

- `git diff`：unstaged；
- `git diff --cached`：staged；
- `git ls-files -z --others --exclude-standard`：untracked。

三类状态分别报告。冻结当前 checkout 的 HEAD，以 `git diff <head>` 独立计算 tracked
净文件数和净行数，不把 staged/unstaged 行数相加：两层可以互相抵消为零净变化。
触及路径数取三个层的字面路径并集（rename 的两端均进入集合），与净 diff 经 rename
检测后的 changed-file 数分开命名。解析特殊文件名时使用 `-z`，不按行或空白拆路径。
untracked 行数即使另行检查统计，也不进入 tracked 净值。

working tree 摘要明确写 `0 个 commit`；与分支组合时两种规模分开，不同 target 和本地
checkout 也不冒称同一上下文。unborn HEAD 只报 staged/unstaged/untracked 层，没有
HEAD-relative 净总计；冲突状态说明限制，不把不完整数字当作普通快照。取证后复查状态，
发现 index/worktree 变动则重新收集或披露，避免把可变状态伪装成不可变 SHA 快照。

### 五部分输出

| 部分 | 回答的问题 | 约束 |
| --- | --- | --- |
| 一句话 | 交付了什么、目的是什么 | 写结果，不写 Agent 操作过程 |
| 比较范围与规模 | 比了哪些不可变提交、改了多少 | 数字必须来自 Git 或说明过的计算 |
| 核心流程/变更链路 | 行为如何形成，或变化如何传递 | 有真实 runtime flow 才使用“业务流程” |
| 主要新增/变更模块 | 哪些目录或包承担核心变化 | 表格给出精确 `+X/-Y`，按模块聚合 |
| 开发演进 | 变化如何形成 | 按证据分 1–6 段；单提交就是一段 |

模板保留稳定的信息顺序，但标题按变化类型调整。功能分支可以使用“核心业务流程”和
“主要新增模块”；修复、重构、删除、配置或文档变化使用中性的“核心变更链路”和
“主要变更模块”。这样既保持读者熟悉的结构，又不强迫 Agent 虚构新增能力。

空比较不制造流程、模块或阶段；detached HEAD 使用 `HEAD@<short-sha>`；没有共同祖先、
浅克隆或对象缺失时，报告证据边界，而不是把 snapshot diff 误写成目标分支引入的变化。

## 执行工作流

```text
解析请求边界
  → 验证 target / baseline
  → 固化 commit SHA 和 merge-base
  → 收集 commit / path / numstat 事实
  → 阅读实际 patch、实现、测试和文档
  → 选择适合变化类型的标题与阶段数
  → 在对话中返回完整报告
  → 用户明确要求保存或交接时，写入 .agents/handoff/
```

取证与成文分离是核心设计：Git 命令负责边界和数字，代码阅读负责语义，语言模型负责压缩。
任何一层证据不足时，结论都应收窄，而不是由下一层补写。

## 持久化策略

普通总结只在对话中返回，避免一次只读问题意外修改工作区。用户明确说保存、归档、交接或
relay 时，才写入：

```text
.agents/handoff/<target>-vs-<base>.md
```

working-tree-only 报告使用 `<target>-working-tree.md`。文件名中不属于
`[A-Za-z0-9._-]` 的字符统一替换为 `-`。写入前检查目录是否被 Git 忽略；写入失败只影响
持久化，不阻断对话中的完整报告。

## 提示词设计原则

1. **先钉死比较范围**：显式 ref 优先，随后才是默认分支发现；SHA 在取证开始前冻结。
2. **机器友好的统计**：使用 `rev-list`、`name-status`、`numstat`，不解析本地化或人类格式的
   `diff --stat` 尾行。
3. **语义来自代码**：commit message 说明演进，不替代对 patch、实现和测试的检查。
4. **模板可识别但不僵硬**：五类信息稳定，标题和阶段数由实际变化决定。
5. **事实与评价分离**：Skill 不输出缺陷、建议或审批判断；这些属于 code review。
6. **副作用按需发生**：默认只读，只有明确交接意图才落盘。
7. **退化而不猜测**：对空历史、无共同祖先、二进制、submodule 和缺失对象给出边界说明。

## 验证策略

`evals/evals.json` 覆盖六类行为：

- 多提交、多模块功能分支；
- 单提交删除型修复；
- staged、unstaged、untracked 并存；
- 生成代码、lockfile、二进制和 rename 占主导；
- target 与 baseline 相同的空比较；
- 产品能力概览等不应触发本 Skill 的近似请求。

这些用例重点验证比较范围、数字口径、标题选择、阶段数量和落盘副作用，而不是只检查
输出中是否出现某些关键词。

## 与相邻机制的关系

| 机制 | 负责什么 | 与 agent-relay 的边界 |
| --- | --- | --- |
| 上下文压缩 | 当前会话对话历史 | agent-relay 以仓库事实为输入，不继承对话中的未经验证声明 |
| AGENTS.md / CLAUDE.md | 长期开发规则 | agent-relay 描述某个 ref 或工作区在一个时点的变化 |
| git log / diff | 原始、完整变化 | agent-relay 做有证据的有损压缩，降低接手成本 |
| code review | 缺陷、风险和建议 | agent-relay 只总结事实，不作质量判断 |
| release notes | 面向用户的发布内容 | agent-relay 面向开发者和 Agent，保留 Git 范围与模块证据 |

它的生态位仍是“会话会结束、分支还在继续”：用一份可复现、低副作用、证据驱动的摘要，
把活跃 Git 状态传递给下一位读者。
