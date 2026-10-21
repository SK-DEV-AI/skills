# searching-codebases

An agent skill that reads the **real source** of a dependency, package or
public repository, **at the exact version in use**, instead of recalling its
API from memory.

## The problem it solves

Ask a base model "what arguments does `Session.request` accept?" and you get a
confident, plausible list. Often the list comes from a **different major
version**, or from a different library with a similar name, or from the
model's imagination. The model cannot tell you which. The result is code that
looks right and fails at runtime, and a user who has no way to know the
description was never checked against the source.

This skill's rule is one line:

> Never describe an API you have not read in the source, at the version the
> user actually has.

## Who it is for

- Developers who have been burned by a "correct-looking" snippet that used a
  parameter removed two majors ago.
- Anyone upgrading a dependency and needing to know what actually changed,
  from the source, not from a blog post.
- Teams doing dependency triage: is this version vulnerable, and what is the
  fixed version.
- Agents that need to orient in an unfamiliar public repository quickly and
  accurately.

## What it does

- **Pins the version before reading anything**, from the user's own manifest
  or lockfile where possible, and states that version in the answer.
- **Reads the source, not a documentation summary**, using package-scoped file
  listing, file reads, and symbol search against npm, PyPI and crates.
- **Quotes the signature** rather than paraphrasing it, and names the file it
  came from. A paraphrase is where the hallucination gets back in.
- **Orders sources by authority**: package source, then stubs and changelog,
  then versioned docs, then registry, then upstream repo, then community
  answers, then search results.
- **Fails honestly.** There is a dedicated output template for "the read did
  not succeed", so a failed lookup is never quietly replaced by a guess.
- **Ships a deterministic helper script** that turns a raw result payload into
  a deduplicated, scored Markdown table, so the agent reads the two files
  worth reading instead of forty.

## Requirements

### 1. The `codesearch` MCP server

The skill drives an MCP server named `codesearch` with these tools:

```
mcp__codesearch__code_search
mcp__codesearch__code_files
mcp__codesearch__code_read
mcp__codesearch__pkg
mcp__codesearch__search_package
mcp__codesearch__search_libraries
mcp__codesearch__vulns
mcp__codesearch__docs
mcp__codesearch__searchcode
mcp__codesearch__analyze
mcp__codesearch__wiki
mcp__codesearch__so_search
mcp__codesearch__hn
mcp__codesearch__papers
mcp__codesearch__search_all
mcp__codesearch__enrich
mcp__codesearch__ping
```

Any MCP client that can register the server works. In Claude Code, add the
server to your MCP configuration (for example `.mcp.json` in the project, or
`claude mcp add` for a user-scoped install) and restart the session.

**The skill ships no credentials.** The server is configured by you, on your
machine, with your own API keys. The skill never reads, stores, or prints a
key, and it never instructs the agent to read environment variables.

### 2. Network access

Required. The server queries live package registries, live code indexes, live
documentation sites and live vulnerability databases. The bundled helper
script makes no network calls at all.

### 3. Python 3.8+ (for the helper script only)

`scripts/normalize_results.py` uses the standard library only. Nothing to
install, nothing to build.

## Installation

**Claude Code (project scope):**

```bash
cp -r searching-codebases .claude/skills/searching-codebases
```

**Claude Code (personal scope):**

```bash
cp -r searching-codebases ~/.claude/skills/searching-codebases
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

Two things to get right: the directory must be named `searching-codebases`
exactly, and `SKILL.md` must be inside it, not one level deeper.

## Usage

Nothing to configure. The skill activates when the request matches its
description, or you can invoke it explicitly with `/searching-codebases`.

Example:

> "I'm on `requests 2.31.0` in this project. What arguments does
> `Session.request` actually accept, and where is it defined?"

The skill reads the pinned version from your manifest, reads
`requests/sessions.py` at that version, and answers with the quoted signature
and the file it came from.

## Permissions

The `SKILL.md` frontmatter pre-approves the MCP tool names so the agent does
not prompt for each call during the turn the skill is active.

**Known issue:** Claude Code issue
[anthropics/claude-code#14956](https://github.com/anthropics/claude-code/issues/14956)
is open, where a skill's `allowed-tools` grant is reported correctly but the
subsequent tool call is still denied. If you hit "This command requires
approval" on an MCP call, allow the `codesearch` server once in your MCP
settings and the skill will work normally from then on.

Agents that do not implement `allowed-tools` simply ignore the field; the
skill still functions, the tools just prompt normally.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Skill never appears in the list | Installed mid-session, wrong directory, or wrong filename | Restart the session; confirm the folder is `searching-codebases` and contains `SKILL.md` directly. |
| "Unknown tool" errors | `codesearch` MCP server not registered | Register the server, then restart the agent. |
| Permission prompt on every MCP call | The `allowed-tools` bug above | Allow the `codesearch` server once in the MCP settings. |
| `code_read` says the file does not exist | Wrong path, or the index lags the release | Run `code_files(spec=...)` to get the real path, then `pkg(action="read")` as a registry fallback. |
| `code_search` with a `target` returns nothing | The package is not indexed for that scope | Use `pkg` instead; check the registry prefix is `npm:`, `pypi:` or `crates:`. |
| Global `code_search` takes 30 seconds | Sourcegraph latency | Set `limit`, wait for the single call, do not retry in a loop. |
| `vulns` response mentions `fallback: osv.dev` | The Sonatype quota or auth failed | Expected. Report the OSV.dev answer and name the database. |
| `analyze` or `wiki` fails or looks stale | Both backends are unofficial scrapes | Use `searchcode(action="file_tree")` and `searchcode(action="get_file")` instead. |
| `normalize_results.py` exits 2 | The input was not valid JSON | Pipe the tool's raw result object, not a truncated copy. Run with `--help` for the accepted shapes. |

## Files in this package

```
searching-codebases/
├── SKILL.md                    the workflow, and when to load each reference
├── LICENSE.txt                 Apache-2.0
├── README.md                   this file
├── references/
│   ├── tools.md                every tool, every parameter, failure modes
│   ├── policy.md               version pinning, source authority, error handling
│   └── templates.md            five output templates
├── scripts/
│   └── normalize_results.py    raw results -> deduplicated, scored table
└── evals/
    └── trigger-eval.json       20-query trigger eval set (10 / 10, 60/40 split)
```

## Safety

- No credentials, keys or tokens are included, requested or printed.
- The bundled script performs no network access, installs nothing, writes no
  files, and reads no environment variables.
- The skill never asks the agent to read environment variables, send user data
  anywhere, or run destructive commands.
- Source files, READMEs and issue text are treated as untrusted data. A file
  in a package cannot instruct the agent to change which repos or packages it
  reads.
- Only the six frontmatter fields defined by the Agent Skills specification
  are used, so the package survives the claude.ai upload path and the Skills
  API without modification.

## License

Apache-2.0. See `LICENSE.txt`.
