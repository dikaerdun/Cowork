# Cowork

这个仓库用于搭建一个带 GitHub 门禁的 AI 评审流程骨架。

当前目标：

- 保证人工审批始终是合并前的最后门槛
- 让 Codex 以结构化 issue 的方式提出评审问题
- 让 Claude 逐条回复，并输出最终给人工看的决策报告
- 在手动闭环跑稳之后，再逐步接入自动化

更多背景见 [docs/ai-review-rollout.md](docs/ai-review-rollout.md)。

## 本地演练

运行本地端到端演练：

```bash
bash scripts/run_local_demo.sh
```

它会启动临时 Claude bridge，把一条示例 Codex issue 送进 Claude worker，并打印回复和最终报告。

## 本地 Web 工作台

启动本地工作台：

```bash
bash scripts/run_local_ui.sh
```

然后打开：

```text
http://127.0.0.1:8080
```

你可以在页面里：

- 粘贴或编辑问题 JSON
- 切换预设模板
- 保存和加载本地模板
- 从真实 PR 评论中导入结构化 issue
- 查看 Claude/bridge 的环境状态
- 查看最近一次运行结果
- 查看运行日志与人工审批摘要
- 点击“开始演练”跑完整流程
