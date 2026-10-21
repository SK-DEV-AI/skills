# researching-the-web

An agent skill that answers questions with **live, multi-engine web search**
and a **citable source list**, instead of the model's memory.

## The problem it solves

Ask a base model "what is the latest version of X" or "is this claim true" and
you get a plausible, confident, dated answer. The model cannot tell you it is
guessing, and it will not refuse. A paragraph of uncited prose also gives you
nothing to check.

This skill swaps recall for retrieval, and swaps unsourced prose for an answer
where **every claim points at a URL you can open**. The payoff is not more
text. It is auditability.

## Who it is for

- Developers and technical writers who ship answers that will be checked.
- Anyone whose work depends on facts that changed after the model's training
  cut-off: versions, prices, CVE status, release notes, legal text, "who won",
  "what is the current state of".
- Teams that have been burned by a confidently wrong "latest version" answer.
- Agents that need a repeatable research workflow rather than a one-off prompt.

## What it does

- Chooses the right tool for the question shape (lookup, deep read, structured
  extraction, academic index, site survey, live browser) instead of defaulting
  to one generic search.
- Reads the pages that actually carry the claim, not just the snippets.
- Enforces a citation policy: numbered sources, a claim-to-source map, dates
  on volatile claims, and a hard ban on citing a URL that was never returned.
- Handles the failure modes honestly: conflicting sources are reported as
  conflicting, unreachable sources are reported as unreachable, and gaps are
  never filled from memory.
- Ships a deterministic helper script that formats raw search results into a
  numbered Markdown source list, so the numbering cannot drift from the inline
  markers.

## Requirements

### 1. The `websearch` MCP server

The skill drives an MCP server named `websearch` with these tools:

```
mcp__websearch__search
mcp__websearch__fetch
mcp__websearch__extract
mcp__websearch__screenshot
mcp__websearch__browser_action
mcp__websearch__wikipedia
mcp__websearch__arxiv
mcp__websearch__map_site
mcp__websearch__pdf_extract
mcp__websearch__ping
```

Any MCP client that can register the server works. In Claude Code, add the
server to your MCP configuration (for example `.mcp.json` in the project, or
`claude mcp add` for a user-scoped install) and restart the session.

**The skill ships no credentials.** The server is configured by you, on your
machine, with your own API keys. The skill never reads, stores, or prints a
key, and it never instructs the agent to read environment variables.

### 2. Network access

Required. The server queries live search engines, live documentation sites,
live Wikipedia and live arXiv. There is no offline corpus behind it. The
bundled helper script makes no network calls at all.

### 3. Python 3.8+ (for the helper script only)

`scripts/format_citations.py` uses the standard library only. No packages to
install, nothing to build.

## Installation

**Claude Code (project scope):**

```bash
cp -r researching-the-web .claude/skills/researching-the-web
```

**Claude Code (personal scope):**

```bash
cp -r researching-the-web ~/.claude/skills/researching-the-web
```

Then **start a new session**. Skills are discovered at session start, so a
skill installed mid-session will not appear until you restart.

**Other agents** that support `SKILL.md` use the same layout. Common paths:

| Agent | Personal skills | Project skills |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenClaw | `~/.openclaw/skills/` | `.openclaw/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Codex CLI | `~/.codex/skills/` | `.codex/skills/` |
| Cursor | n/a | `.cursor/skills/` (project only) |

Two things to get right: the directory must be named `researching-the-web`
exactly, and `SKILL.md` must be inside it, not one level deeper.

## Usage

Nothing to configure. The skill activates when the request matches its
description, or you can invoke it explicitly with `/researching-the-web`.

Example:

> "Is it true that Postgres 18 dropped MD5 password support? I need to check
> this before I tell our security team."

The skill will search for the claim, fetch the primary source, and answer with
a dated claim and a numbered source list.

## Permissions

The `SKILL.md` frontmatter pre-approves the MCP tool names so the agent does
not prompt for each call during the turn the skill is active.

**Known issue:** Claude Code issue
[anthropics/claude-code#14956](https://github.com/anthropics/claude-code/issues/14956)
is open, where a skill's `allowed-tools` grant is reported correctly but the
subsequent tool call is still denied. If you hit "This command requires
approval" on an MCP call, allow the `websearch` server once in your MCP
settings and the skill will work normally from then on.

Agents that do not implement `allowed-tools` simply ignore the field; the
skill still functions, the tools just prompt normally.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Skill never appears in the list | Installed mid-session, wrong directory, or wrong filename | Restart the session; confirm the folder is `researching-the-web` and contains `SKILL.md` directly. |
| "Unknown tool" errors | `websearch` MCP server not registered | Register the server, then restart the agent. |
| Permission prompt on every MCP call | The `allowed-tools` bug above | Allow the `websearch` server once in the MCP settings. |
| `synthesis` field missing from results | No synthesis provider configured on the server | Nothing to do. The skill writes the answer itself from fetched sources. |
| `relevance_score` is `0.0` for every result | The server's local reranker is not running | Results are still valid, just engine-ordered. Not an error. |
| `engine_blocked` in the response | Some engines are rate-limited from your network | Normal. The server routes around them; check `engines_used`. |
| `fetch` returns a page with almost no text | The page needs JavaScript | The skill falls back to `browser_action`. |
| `format_citations.py` exits 2 | The input was not valid JSON | Pipe the tool's raw result object, not a truncated copy. Run with `--help` for the accepted shapes. |

## Files in this package

```
researching-the-web/
├── SKILL.md                    the workflow, and when to load each reference
├── LICENSE.txt                 Apache-2.0
├── README.md                   this file
├── references/
│   ├── tools.md                every tool, every parameter, failure modes
│   ├── policy.md               source selection, citation rules, error handling
│   └── templates.md            four output templates
├── scripts/
│   └── format_citations.py     raw results -> numbered source list + claim map
└── evals/
    └── trigger-eval.json       20-query trigger eval set (10 / 10, 60/40 split)
```

## Safety

- No credentials, keys or tokens are included, requested or printed.
- The bundled script performs no network access, installs nothing, writes no
  files, and reads no environment variables.
- The skill never asks the agent to read environment variables, send user data
  anywhere, or run destructive commands.
- Fetched web pages are treated as untrusted data. A page cannot instruct the
  agent to change which URLs it visits or what it reports.
- Only the six frontmatter fields defined by the Agent Skills specification
  are used, so the package survives the claude.ai upload path and the Skills
  API without modification.

## License

Apache-2.0. See `LICENSE.txt`.
