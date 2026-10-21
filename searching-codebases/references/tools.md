# codesearch tool reference

Every tool, every parameter, what it returns, and how it fails.

All tool names below are MCP tools on the `codesearch` server. In a client
that exposes MCP tools by their fully-qualified name they are called as
`mcp__codesearch__<tool>`.

---

## Package-scoped source reading (the core of this skill)

### `code_files`

List the files inside an indexed published package.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `spec` | string | required | `registry:name[@version]`, e.g. `npm:express`, `pypi:requests@2.32.3`, `crates:serde`. |
| `path_prefix` | string | - | Restrict to a path prefix, e.g. `src/`. |

**Returns** a file listing with paths and sizes.

**Failure modes**

- Indexes **npm, PyPI and crates only**. A `github:` spec is rejected.
- A version can be absent from the index even though it exists in the
  registry. That is an index gap, not proof the package is missing. Fall back
  to `pkg(action="files")`.

### `code_read`

Read one file out of an indexed published package, verbatim.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `spec` | string | required | `registry:name[@version]`. |
| `path` | string | required | Path inside the package, e.g. `src/index.js`. |

**Returns** the file content.

**Failure modes**

- Wrong path -> an error naming the path, or an empty result. Use
  `code_files` to get the real path; do not guess paths.
- The index may lag the published tarball. If the file is missing, retry with
  `pkg(action="read")`, which goes to the registry.

### `code_search`

Search code, docs and symbols, either inside one package or across public
repositories.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | required | The search expression. Supports implicit AND, `OR`, parentheses, `-exclude`, and qualifiers such as `kind:`, `category:`, `lang:`, `path:`. |
| `target` | string | - | Package scope `registry:name[@version]`. Omit for a global public-repository search. |
| `source` | enum | - | `docs`, `code`, `symbol`. `symbol` returns declarations. |
| `lang` | string | - | Language filter. |
| `limit` | int | 10 | Max results, 1-100. |

**Returns** matching code, docs or symbols, with file and line information.

**Failure modes**

- A package-scoped search needs the index to have that package. If it has
  not been indexed, use `code_files`/`code_read` first, or `pkg`.
- The global mode is Sourcegraph: 8 to 30 seconds per query. Set `limit`, be
  patient, and do not retry in a loop.
- Long natural-language queries match nothing. Search for a symbol or a
  distinctive string.

---

## `pkg`

Package intelligence: metadata, changelog, upgrade review, file list, file
content.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | `info` | `info`, `changelog`, `upgrade_review`, `files`, `read`. |
| `name` | string | required | Package name. |
| `registry` | string | `auto` | `npm`, `pypi`, `crates`, or auto-detect. |
| `version` | string | latest | Version to read. |
| `current_version` | string | - | `upgrade_review`: the version in use. |
| `target_version` | string | - | `upgrade_review`: the version to move to. |
| `from_version` / `to_version` | string | - | `changelog`: the range. |
| `path` | string | - | `files`: a path filter. `read`: the exact path. |
| `count` | int | 10 | Number of changelog entries. |

**Returns** composite package metadata (Libraries.io plus Sonatype plus the
package index), release notes, a vulnerability-plus-changelog-plus-dependency
diff between two versions, a file listing, or a file's content.

**Failure modes**

- `info` merges several sources, so a field can be absent because one source
  was unreachable. For a version fact, use `search_package` and read the
  registry directly.
- `upgrade_review` needs both versions to exist.

### `search_package`

Raw registry queries, one source, no merging. This is the fast, exact path
for version facts.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | required | Package name. |
| `registry` | string | `auto` | `npm`, `pypi`, `crates`, or auto. |
| `action` | enum | - | `npm_versions`, `pypi_versions`, `crates_versions`, `npm_dist_tags`, `npm_get_version`, `pypi_get_version`, `crates_get_version`, `npm_get_readme`, `crates_summary`, `depsdev_dependencies`, `depsdev_info`, `depsdev_advisory`, `depsdev_query`, `npm_time`, `crates_downloads`, `crates_reverse_deps`, `crates_owners`, `crates_categories`, `crates_keywords`, `npm_search`, `crates_search`. |
| `version` | string | - | The version, for version-specific actions. `latest` resolves to newest. |
| `advisory_id` | string | - | OSV advisory id for `depsdev_advisory`. |
| `hash_type` / `hash_value` | string | - | For `depsdev_query`. |

**Returns** registry data for exactly what was asked.

**Failure modes**: a package that does not exist on the queried registry
returns empty. Re-check the registry name and the spelling.

### `search_libraries`

Libraries.io dependency metadata and source rank.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `name` | string | - | Project name. |
| `platform` | string | `""` | `npm`, `pypi`, `crates`, ... |
| `query` | string | - | Free-text search. |
| `action` | enum | - | `versions`, `dependencies`, `dependents`, `github_repo`, `github_dependencies`, `platforms`, `licenses`, `keywords`. Omit for a project search. |
| `version` | string | - | Version. |
| `owner` / `repo` | string | - | For the GitHub actions. |
| `keyword` | string | - | For `keywords`. |
| `sort` / `languages` / `licenses` | string | - | Filters. |
| `count` | int | 10 | Result count. |

**Returns** dependency counts, dependents, the GitHub repository behind a
package, licences, keywords.

**Failure modes**: the data is uncurated and can be stale. Use it for source
rank and dependents, **never for version facts**.

---

## `vulns`

Vulnerability scanning and detail, Sonatype Guide with a keyless OSV.dev
fallback.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | - | `scan`, `detail`, `latest_version`, `license`. |
| `platform` | string | - | `npm`, `pypi`, `crates`, `maven`, ... |
| `name` | string | - | Package name, for `scan`. |
| `version` | string | - | Version, for `scan`. |
| `coordinates` | string | - | Alternative package coordinates. |
| `vuln_id` | string | - | For `detail`: a Sonatype id, a `GHSA-` id, or a `CVE-` id. |
| `purl` | string | - | Package URL, for `latest_version` and `license`. |

**Returns** the vulnerability list for the scanned package, or the detail of
one advisory.

**Failure modes**

- On a Sonatype auth, quota or rate-limit error the tool falls back to
  OSV.dev automatically. The response says so. When it does, report the OSV
  answer, and say which database it came from.
- `scan` needs the exact version. Scanning `latest` tells you about a version
  the user does not have.

---

## `docs`

Documentation lookup, with a quota-free-first fallback chain:
ReadTheDocs, then DevDocs, then `llms.txt`, then Context7.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | `search` | `search`, `devdocs_search`, `devdocs_fetch`, `devdocs_fetch_content`, `devdocs_list`, `devdocs_meta`, `devdocs_toc`, `rtd_search`, `rtd_info`, `rtd_versions`, `rtd_builds`, `rtd_translations`, `rtd_subprojects`, `context7_add_repo`. |
| `query` | string | - | What to look for. |
| `library` | string | - | Library name. |
| `library_id` | string | - | Context7 library id, to skip the search. |
| `version` | string | - | Documentation version. |
| `slug` | string | - | DevDocs slug. |
| `path` | string | - | DevDocs path. |
| `project` / `provider` / `repo_url` | string | - | `context7_add_repo` inputs. |
| `fast` | bool | - | Skip the slower enrichment. |

**Returns** doc search results, metadata, a table of contents, or full
content.

**Failure modes**

- Documentation describes the **latest** release, not necessarily the
  version the user has. A doc page is not a version-pinned source; the
  package source is.
- The Context7 lane has a small monthly quota and the tool tries the
  quota-free sources first for that reason.

---

## Public repository intelligence

### `analyze`

One call, several sources in parallel: GitHub metadata, code-quality
findings, DeepWiki architecture, CodeWiki sections.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `repository` | string | required | GitHub URL or `owner/repo`. |

**Returns** languages, complexity, tech stack, credential surface, entry
points, architecture, and a directory tree.

**Failure modes**: it takes 10 to 15 seconds. It is built on unofficial
scrapes and can fail or go stale. Treat it as an orientation tool, not as
ground truth: confirm anything important with `searchcode` or the source.

### `searchcode`

Per-repository code intelligence, no auth, no rate limit.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | - | `analyze`, `search`, `findings`, `file_tree`, `get_file`. |
| `repository` | string | required | Git URL or `owner/repo`. |
| `query` | string | - | Search term, for `search`. |
| `path` | string | - | Subdirectory filter. |
| `language` | string | - | Language filter. |
| `detail_level` | enum | `summary` | `summary` or `full`, for `analyze`. |
| `symbol_name` | string | - | Function or class to extract, for `get_file`. |
| `case_sensitive` | bool | false | For `search`. |
| `context_lines` | int | 2 | Context lines around matches. |
| `max_results` | int | 10 | Result cap. |
| `severity` | enum | - | `error`, `warning`, `info`, for `findings`. |
| `category` | enum | - | `security`, `deprecated`, `safety`, `correctness`, `maintainability`, `accessibility`, `modernization`, `performance`, `concurrency`. |
| `start_line` / `end_line` | int | - | Line range, for `get_file` without a symbol. |

**Returns** a repo overview, code matches, quality findings, a file tree, or
a file's content.

**Failure modes**

- `get_file` without `symbol_name` needs `start_line`/`end_line` or a full
  read; without them you get the head of the file.
- `findings` are heuristic. A reported issue is a lead to verify, not a
  confirmed defect.

### `wiki`

Repository architecture and wiki, via DeepWiki and CodeWiki.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | - | `search`, `fetch`, `ask`, `architecture`. |
| `owner` + `repo` | string | - | Single repository. |
| `repos` | string[] | - | Up to 10 `owner/repo` strings for `ask`. |
| `question` | string | - | The question, for `ask`. |
| `wiki_name` | string | - | Page name, for `fetch`. |
| `query` | string | - | Search text. |
| `limit` | int | 5 | Result cap. |
| `offset` | int | 0 | Pagination. |

**Returns** wiki pages, a direct answer, or an architecture summary.

**Failure modes**: both backends are unofficial scrapes, and CodeWiki depends
on an internal RPC that can disappear. When a wiki answer conflicts with the
source, the source wins.

---

## Community and discussion

### `so_search`

Stack Overflow, via the Stack Exchange API or the SOFA agent-contributed
source.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | `stackexchange` | `stackexchange`, `sofa`, plus the Stack Exchange sub-actions `questions_by_ids`, `search_users`, `search_tags`, `question_comments`, `questions`, `answers`, `users`. |
| `query` | string | - | Search text. |
| `count` | int | 5 | Result count. |
| `tags` | string | - | Tag filter. |
| `accepted` | bool | - | Only accepted answers. |
| `closed` | bool | - | Exclude closed questions. |
| `sort` | enum | `relevance` | `relevance`, `votes`, `activity`, `creation`. |
| `type` | enum | `search` | `search`, `excerpts`, `faq`, `answers`, `similar`, `tags_info`, `tags_wikis`. |
| `site` | string | `stackoverflow` | Stack Exchange site. |
| `question_id` / `ids` | int/string | - | Look up specific questions or answers. |
| `page` | int | 1 | Pagination. |
| `fromdate` / `todate` | string | - | Unix timestamp or date string. |
| `views` / `answers` | int | 0 | Minimum counts. |
| `content_type` | enum | `question` | SOFA only: `question`, `til`, `blueprint`, `playbook`. |
| `post_id` / `steering` | string | - | SOFA only. |

**Returns** questions and answers with scores, tags, view counts and
acceptance state.

**Failure modes**

- The keyless Stack Exchange quota is 300 requests per day per IP. On
  exhaustion the tool reports it.
- The `sofa` action needs a configured provider key. Without it, use
  `stackexchange`.
- An accepted answer is a strong signal, not proof. Confirm the behaviour
  against the source.

### `hn`

Hacker News.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | - | `search`, `item`, `stories`, `user`. |
| `query` | string | - | Search text. |
| `count` | int | 5 | Result count. |
| `tags` | enum | `story` | `story`, `comment`, `poll`, `front_page`, `ask_hn`, `show_hn`. |
| `min_points` / `min_comments` | int | 0 | Thresholds. |
| `sort_by_date` | bool | - | Newest first. |
| `item_id` | int | - | For `item`. |
| `firebase_type` | string | - | Hacker News API type filter. |
| `username` | string | - | For `user`. |

**Returns** stories, comments, and user profiles with points and comment
counts.

**Failure modes**: Hacker News is opinion, not documentation. Use it for
"what is the community saying" and never as the authority on an API.

### `papers`

Academic papers from Semantic Scholar, CORE, arXiv and OpenAlex.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | - | `search`, `details`, `batch`, `citations`, `references`, `recommendations`, `author_search`, `author_papers`, `autocomplete`, `core_search`, `author_by_id`, `bulk_search`, `recommendations_negatives`, `arxiv_search`. |
| `query` | string | - | Topic query. |
| `paper_id` / `paper_ids` | string | - | For `details` and `batch`. |
| `author_id` | string | - | For author actions. |
| `count` | int | 10 | Result count. |
| `offset` | int | 0 | Pagination. |
| `year` | string | - | Year filter. |
| `fields_of_study` | string | - | Domain filter, e.g. `Computer Science`. |
| `open_access` | bool | - | Open-access only. |
| `positive_ids` / `negative_ids` | string | - | For `recommendations_negatives`. |

**Returns** paper records with titles, authors, abstracts, years, citation
counts and identifiers.

**Failure modes**: the multi-source fallback order is Semantic Scholar, then
arXiv, then OpenAlex, then CORE. A response may come from a later source
because an earlier one was unavailable. CORE is demoted last because it has
no citation graph.

---

## Discovery and enrichment

### `search_all`

Unified search across 14+ sources with embedding deduplication and reranking.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | required | The query. |
| `library` / `version` | string | - | Library and version filters. |
| `owner` / `repo` | string | - | Repository filters. |
| `language` | string | - | Language filter. |
| `count` | int | 10 | Results per source, max 50. |
| `fields_of_study` | string | - | Semantic Scholar domain filter. |
| `so_sort` | enum | `votes` | `votes`, `activity`, `creation`, `relevance`. |
| `fromdate` / `todate` | string | - | ISO date filters. |
| `synthesize` | bool | true | Groq-written answer with citations. |

**Returns** a merged, deduplicated, reranked result set.

**Failure modes**

- It is a discovery tool, not a precision tool. For "what is the signature in
  this exact version", call the specific tool.
- `synthesize` no-ops without a configured provider. Everything else still
  works.

### `enrich`

Fetch full content for a list of results, deduplicate and rerank.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | required | The original query, for reranking. |
| `results` | object[] | required | Objects with `url`, `title`, `text` or `snippet`, `source`. |
| `top_k` | int | 20 | Max enriched results returned. |
| `max_fetch_size` | int | 50 | Max results fetched. |
| `include_html` | bool | false | Keep raw HTML. |

**Returns** the enriched, deduplicated, reranked results.

**Failure modes**: it fetches the URLs you give it, so only pass URLs that
came out of a search result. Fetching arbitrary URLs turns a search tool
into an open proxy.

### `ping`

Connectivity check, no parameters. Use it once when calls are failing, not
on every call.
