# Agent Skills for web research and codebases

Two production skills for AI coding agents, built on top of the
[websearch](https://github.com/SK-DEV-AI/websearch) and
[codesearch](https://github.com/SK-DEV-AI/codesearch) MCP servers.

| Skill | MCP server | What it fixes |
|---|---|---|
| [`researching-the-web`](researching-the-web/) | `websearch` | Answers from live, multi-engine, reranked sources with citations — instead of the model's memory, which cannot tell you it is guessing. |
| [`searching-codebases`](searching-codebases/) | `codesearch` | Reads the real source of a dependency **at the exact version in use** — instead of recalling a plausible-but-wrong API from a different major version. |

## Install

With the [skills](https://skills.sh) CLI:

```bash
npx skills add SK-DEV-AI/skills
```

Or copy one skill directory into your agent's skills folder:

| Agent | Personal | Project |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.codex/skills/` | `.codex/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| OpenClaw | `~/.openclaw/skills/` | `.openclaw/skills/` |
| Cursor | — | `.cursor/skills/` (project only) |

The skill name must equal the folder name, and the file must be exactly
`SKILL.md` (uppercase). Start a new session after installing.

## Requirements

Each skill needs its MCP server connected. Both are open source, MIT licensed,
and run locally:

- [websearch](https://github.com/SK-DEV-AI/websearch) — multi-engine web search,
  fetch, PDF/extract, and a real-browser tool.
- [codesearch](https://github.com/SK-DEV-AI/codesearch) — code, package, docs,
  paper, and vulnerability search.

```bash
git clone https://github.com/SK-DEV-AI/websearch.git
cd websearch && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp run.example run   # optional API keys; keyless lanes work without them
chmod +x run
```

Point your MCP client at the `run` script:

```json
{ "websearch": { "command": "/path/to/websearch/run" } }
```

**Note on permissions:** the skills pre-approve their MCP tools with
`allowed-tools`, but some agent versions (a known Claude Code bug) still show a
one-time approval prompt the first time. Allow the MCP server once and it
works from then on.

## What is in each skill

```
<skill-name>/
├── SKILL.md          # the workflow
├── LICENSE.txt
├── README.md
├── references/       # tool-by-tool detail, policy, output templates
├── scripts/          # deterministic helpers (not prose)
└── evals/            # 20-query trigger eval set
```

The `references/` files are loaded only when the skill needs them, so the
always-loaded context stays small. The `scripts/` are deterministic — the agent
runs them and only the output enters the conversation.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Security

These skills make no outbound calls of their own. They instruct the agent to
call the MCP servers, which the **user** configures and authenticates. No
skill reads environment variables, ships credentials, or downloads code at
runtime. See each skill's README for details.
