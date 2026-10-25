# websearch tool reference

Every tool, every parameter, what it returns, and how it fails.

All tool names below are MCP tools on the `websearch` server. In a client that
exposes MCP tools by their fully-qualified name they are called as
`mcp__websearch__<tool>`.

> **Run `doctor` first on an unfamiliar install.** It reports which lanes are
> live and prints the exact command for the rest. Several features here are
> optional and stay silent when absent — an empty result is often "needs
> setup", not "broken".

---

## `doctor`

Lane preflight. Call it when a search returns nothing, before you conclude
something is broken, or once at the start of a session on a machine you have
not used before.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `probe_network` | bool | `true` | Run an outbound HTTPS check (adds ~1s). Set `false` for an instant report. |

Returns `summary` (`live` / `needs_setup` / `off` counts), a `lanes` array
where each entry carries `status`, `requires`, `how_to_enable` and `note`, plus
`where_am_i` (`local` vs headless server) and an `env` block. It reports which
key variable NAMES are set, never their values.

Key distinction it makes for you: the **keyless HTTP lanes** work anywhere,
including a headless server. The **browser lanes** — Google AI Mode,
`browser_action`, and the CDP fallback for bot-walled pages — need a
Chromium-based browser with `--remote-debugging-port` running on the same host,
and so cannot work on a server with no signed-in browser. Cross-encoder
reranking is optional and absent by default on a fresh install.

---

## `search`

Multi-engine web search with dedup, reranking and optional synthesis.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | required | The question, in the user's words. |
| `count` | int | 10 | Results to return. |
| `depth` | int | 1 | `1` = snippets only. `2+` = fetch full pages and re-rank. |
| `search_type` | enum | `auto` | `auto`, `text`, `news`, `images`, `videos`, `books`. |
| `timelimit` | string | - | Recency filter: `d`, `w`, `m`, `y`. |
| `safesearch` | enum | `moderate` | `off`, `moderate`, `strict`. |
| `language` | string | `en` | Content language. |
| `start_date` / `end_date` | string | - | Tavily date range, `YYYY-MM-DD`. |
| `include_domains` / `exclude_domains` | string[] | - | Pin the source set. |
| `synthesize` | bool | `true` | Groq-written answer with `[N]` citations. |
| `domain` | string | - | AnySearch vertical: `finance`, `code`, `academic`, `health`, `travel`, `legal`, `security`. Guessed from the query if omitted, which can be wrong. |
| `anysearch_tag` | string | - | Precise vertical tag, e.g. `code.doc`. Overrides `domain`. |
| `anysearch_zone` | enum | `""` | `cn` or `intl`. |
| `anysearch_language` | string | - | e.g. `en`, `zh-CN`. |
| `google_ai_only` | bool | `false` | Skip every other engine and use Google AI Mode only. **Requires a signed-in Chromium over CDP**; without one this returns a structured error naming the cause and the fix, not results. |
| `history` | string | - | Conversation context so pronouns resolve ("the second one"). |
| `upload_urls` | string[] | - | Files for Google AI Mode: images, PDF, max 10 MB, one per call. |

**Returns** a result set. Useful fields: `results[]` (each with `title`, `url`,
`snippet`, `relevance_score`, optionally `fetch_relevance` and full text at
`depth>=2`), `engines_used[]`, `engine_blocked[]`, `synthesis` (when enabled),
`answer`.

**Failure modes**

- `relevance_score` all `0.0` -> the local reranker is not running. Results are
  still valid, just engine-ordered.
- `engine_blocked` non-empty -> some engines are rate-limited from this
  network. The server routes around them; check `engines_used`.
- `synthesis` missing or "not configured" -> no Groq key configured. Search
  still works; only synthesis and query rewriting are off.
- Thin result set -> widen `count`, drop `include_domains`, or use `depth=2`.

---

## `search` synthesis quality

Search synthesis is the cited answer returned in the `synthesis` field of a
`search` call. Prompt version shipped: 2026-10-25.2.

**Prompt rules**

- No invention. Only the supplied results may be used; a claim that cannot be
  cited is deleted. If the results do not answer the question, it says so and
  stops.
- Unbiased. "Rank is not evidence." Disagreement between sources is reported
  with each side attributed, never averaged into one figure. A false premise in
  the question is corrected. Vendor/marketing claims are labelled as such. A
  claim from a single source is marked "(single source)".
- Concise by construction. Answer in the first sentence, no preamble, ceiling
  of 6 sentences (12 with `synthesize_length="long"`), with a one-line example
  of the expected shape. Filler phrases are banned by name. The sentence cap is
  the length control; the token budget is only a safety net, because models
  follow structural targets far more reliably than token counts.
- Injection defence. Results are wrapped in delimiters carrying a random
  per-request suffix (`<results-9f3a1c> ... </results-9f3a1c>`), so a page cannot
  close the container by containing its own closing tag, and the content is
  declared untrusted data. Text in a page that looks like an instruction is
  ignored, that result is excluded, and the answer ends with
  `Ignored instruction-like text in [N].` This shifts a probability; it is not a
  guarantee against an adaptive attacker.

**Returned fields on `synthesis`**

`prompt_version` (string), `model`, `provider` (`local` or `groq`),
`temperature` (always 0.0), `finish_reason`, `truncated` (true when
`finish_reason=length`), `sources_used`, `sources[]`, `diversity`
(`{n_domains, domains[], per_domain_effective, relaxed, duplicate_domains,
requested, returned}`), `grounded` (`{flagged[], ok, checked_by,
advisory:true}` when the verifier returns a verdict), `attempts`,
`endpoints_tried[]`, `duplicates_removed`, `figures_unverified[]`,
`citations_used`, `as_of`, `duplicates_removed`, `figures_unverified[]`,
`duration_ms`, and `cached` when the answer was served from cache. When there is no answer: `skipped` or `error` plus a note.

`citations_used` counts the sources the answer actually cites, which need not be
all of them. When it is 1 and more sources were retrieved, the text gains a
visible "[This answer cites one source of the N retrieved...]" line.

`figures_unverified` is the cheapest check and needs no model: any number in the
answer that appears in none of the cited text was produced by the model, so it
is either a recomputation or an invention. The same list is appended to the
answer text as a visible marker. `duplicates_removed` counts syndicated copies
of one article that were collapsed before the answer was written.

**Defaults and knobs**

- `depth` default 3 when a model lane is configured, 1 when not.
  `WEBSEARCH_DEFAULT_DEPTH` pins it. Explicit `depth` always wins. Range 1-5.
  Depth also sizes the page fetch (`max(5, depth*2)`, ceiling 8 via
  `WEBSEARCH_ENRICH_MAX_PAGES`), so it changes how much evidence the model sees,
  not just a label. Measured: depth 3 averages 4.75 source domains and 3.5
  citations versus 2.5 and 2.25 at depth 1, at no extra wall time over depth 2.
- `synthesize` defaults to true. `synthesize_length` is `short` (6 sentences) or
  `long` (12).
- `WEBSEARCH_SYNTH_PROVIDER`: `local` (default; in-tool model first, Groq
  fallback) | `groq` | `auto`.
- `WEBSEARCH_SYNTH_TOKENS`: 900. `WEBSEARCH_SYNTH_MAX_SOURCES`: 8.
  `WEBSEARCH_DOMAIN_CAP`: 2. `WEBSEARCH_MIN_SOURCES`: 3.
  `WEBSEARCH_SYNTH_SNIPPET_CHARS`: 1500.
- The verifier is given the same source excerpts the synthesis saw. Its output
  is marked advisory (`grounded.advisory: true`) because it is another model's
  opinion, not proof.

**Known behaviours**

- With no model endpoint configured, `search` still returns ranked results and
  `synthesis.skipped` explains why there is no written answer. It is never blank.
- An answer cut off by the token budget is labelled `truncated: true` and ends
  with a visible `[truncated at N tokens ...]` marker.
- If the answer cites only one of the retrieved sources, the text says so.
- Junk page titles are rejected: metadata like "Keyboard shortcuts" (mdbook) or
  a synthetic fetch label is not the page's subject, so it falls back to the first
  heading rather than being shown as a title.
- Sources with a publication date are sent to the model as `Published: ...`;
  undated ones are labelled `not stated`. `as_of` on the result is the newest
  source date, so staleness is visible rather than guessed.
- A repeated search can return `cached: true`. The cache key includes the source
  text itself, so an edited page produces a fresh answer rather than a stale one.

---

## `fetch`

URL to markdown or text. Auto-fallback: direct fetch, then a headless browser
for blocked or JS-rendered pages. Supports PDF, EPUB and DOCX. SSRF-protected.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Target URL. |
| `max_chars` | int | 5000 | Characters returned per call. |
| `offset` | int | 0 | Character offset for paginated reads. |
| `focus` | string | - | BM25 relevance filter. Use only to pull one section out of a long page. |
| `cache_ttl` | int | 3600 | Cache seconds. `0` forces a fresh fetch. |
| `css_selector` | string | - | Extract only this element (browser tier only). |
| `extraction_type` | enum | `markdown` | `markdown`, `text`, `html`. |
| `output_format` | enum | `markdown` | `markdown`, `txt`, `json`, `xml`, `csv`. |
| `target_language` | string | - | Translate the output. |
| `raw` | bool | false | Skip extraction, return raw text (good for raw file hosts). |
| `network_idle` | bool | true | Wait for network idle before extracting (browser tier only). |
| `include_images` / `include_links` / `include_formatting` / `include_tables` | bool | true | Output richness switches. |
| `start_line` / `end_line` | int | - | 1-based inclusive line slice. |
| `quality_floor` | number | 0 | Minimum acceptable extraction quality, 0-1. Below it the result is flagged `low_quality`. |
| `mineru` | bool | false | Heavy CPU re-extraction for low-quality pages. |
| `cookies` | object[] | - | Cookies injected into the request, for a page behind a login the user has. |
| `fast` | bool | - | Skip the slow extraction path. |
| `distill` | bool | `false` | Compress the page with a local model before returning it. Opt-in; never default. The result states whether it was distilled, the raw size, and how to get the raw text back. Skipped below the size threshold. |
| `distill_question` | string | - | What you are looking for. Focuses the distiller so it is less likely to drop the detail you needed. |

**Returns** `content` (markdown or text), plus `is_truncated`, `next_offset`,
`total_extracted_chars`, and a quality flag.

**Failure modes**

- Page shell with little content -> the page needs JavaScript. Use
  `browser_action`.
- `is_truncated` true and `next_offset` present -> you did not read the whole
  page. Page again with `offset=next_offset` if the missing part matters.
- `focus` dropped content -> it is a semantic filter, not a literal one. Omit
  `focus` and read the whole page.
- Low-quality extraction -> raise `quality_floor` acceptance, or try
  `mineru=true` for a heavy re-extraction.

---

## `extract`

Structured JSON out of a webpage, by CSS selector, regex, or LLM. Cached, so
repeat calls are free.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Target URL. |
| `instruction` | string | - | Natural-language extraction instruction (LLM strategy). |
| `strategy` | enum | `css` | `css` (fast, free), `llm` (accurate, costs quota), `regex` (emails, phones, URLs). |
| `fields` | string[] | - | Field names to pull. |
| `chunk_threshold` | int | 2000 | Max tokens per chunk in LLM mode. |
| `css_selector` | string | `body` | Container element for CSS strategy. |
| `provider` | string | `groq/openai/gpt-oss-120b` | LLM provider in LiteLLM format. |

**Returns** a JSON object keyed by the requested fields.

**Failure modes**: `strategy="llm"` needs a configured provider; without one
use `css` or `regex`. CSS fields that do not exist come back empty rather than
erroring.

---

## `screenshot`

ARIA accessibility snapshot: the page's text and structure, LLM-readable.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Target URL. |
| `max_chars` | int | 10000 | Cap on returned snapshot text. |
| `depth` | int | - | Accessibility tree depth limit. |
| `verbose` | bool | false | Show all ARIA roles, not just interactive ones. |
| `start_line` / `end_line` | int | - | Line slice of the snapshot text. |

**Returns** the page's visible text and interactive structure.

**Failure modes**: it is a snapshot, not an article extractor. For readable
prose use `fetch`. Interactive elements that are not exposed as ARIA nodes stay
invisible to it.

---

## `browser_action`

Drive a real headless browser: navigate, click, type, press a key, evaluate
JavaScript, read HTML or text, read the accessibility tree, capture a PNG.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | - | `navigate`, `click`, `type`, `key`, `evaluate`, `html`, `text`, `aria`, `screenshot`, `wait`. |
| `url` | string | - | Required for `navigate`; optional for other actions. |
| `selector` | string | - | Required for `click`; focus target for `type`; element for `text`. |
| `text` | string | - | Text to type. |
| `key` | string | - | DOM key value: `Enter`, `Escape`, `Tab`, `ArrowDown`. |
| `expression` | string | - | JavaScript expression for `evaluate`. Arrow functions are auto-invoked. |
| `wait_state` | enum | `domcontentloaded` | `domcontentloaded`, `load`, `networkidle`. |
| `session_id` | string | - | Reuse a persistent tab from `browser_session(action='create')` instead of opening a throwaway one. Required for anything stateful across calls: logins, cookies, multi-page flows, forms. Without it, each call gets a fresh tab that is closed afterwards. |
| `steps` | object[] | - | Ordered multi-step flow in ONE tab, max 25 steps, same fields as above. |
| `timeout` | number | 30 | Per-step timeout in seconds, 1-120. |
| `max_chars` | int | 20000 | Cap for `html`, `text`, `aria`. |
| `full_page` | bool | true | `screenshot` only: capture beyond the viewport. |
| `image_type` | enum | `png` | `png` or `jpeg`. |
| `quality` | int | - | JPEG quality 0-100. |
| `depth` | int | 5 | `aria` tree depth, 1-100. |

**Returns** the requested content, or a path to the written PNG for
`screenshot`.

**Failure modes**: one call is one fresh tab, closed afterwards, so state does
not survive between calls unless you use `steps[]`. URLs are SSRF-validated.
A bot wall or a CAPTCHA can still block the page; report that rather than
looping.

---

## `wikipedia`

Full Wikipedia API client.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | `search` | `search`, `summary`, `summary_action`, `categories`, `links`, `pageviews`, `extlinks`, `categorymembers`, `revisions`, `backlinks`, `recentchanges`, `geosearch`, `random`, `langlinks`, `allpages`. |
| `query` | string | - | Search text or title. |
| `count` | int | 3 | Result count. |
| `language` | string | `en` | Wiki language. |
| `category` | string | - | For `categorymembers`, without the `Category:` prefix. |
| `namespace` | int | 0 | 0 = articles, 14 = categories. |
| `days` | int | 30 | Pageview history window. |
| `type_filter` | string | - | `recentchanges` type: `edit`, `new`, `move`, `log`, `categorize`. |
| `include_images` | bool | false | Thumbnails in `summary_action`. |
| `lat` / `lon` / `distance` | number | 1000 | `geosearch` centre and radius in metres. |

**Returns** article text, summaries, metadata or change lists depending on the
action.

**Failure modes**: a missing article returns a "no such page" style response
rather than an error. Wikipedia is a good tie-breaker for encyclopedic facts
and a poor source for anything recent.

---

## `arxiv`

Search arXiv. Single source.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | required | Search text. |
| `count` | int | 3 | Result count. |
| `search_field` | enum | `all` | `all`, `ti`, `au`, `abs`, `cat`, `co`, `jr`, `id`. |
| `sort_by` | enum | `relevance` | `relevance`, `lastUpdatedDate`, `submittedDate`. |
| `sort_order` | enum | `descending` | `ascending` or `descending`. |
| `start` | int | 0 | Pagination offset. |
| `id_list` | string | - | Comma-delimited arXiv IDs. |
| `category` | string | - | arXiv category filter, e.g. `cs.AI`. |
| `raw_query` | string | - | Raw arXiv syntax with `AND`, `OR`, `ANDNOT`, phrase and wildcard search. Overrides `query` and `search_field`. |

**Returns** paper records with title, authors, abstract, dates and identifiers.

**Failure modes**: single-source and rate-limited. For multi-source paper
search across Semantic Scholar, arXiv, OpenAlex and CORE use the codesearch
server's `papers` tool.

---

## `map_site`

Discover the pages of a website via sitemap XML, falling back to HTML link
extraction.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Site to map. |
| `max_urls` | int | 1000 | Cap on returned URLs. |
| `max_depth` | int | 0 | Recursive link depth when there is no sitemap. |
| `include_sitemap` | bool | true | Try sitemap discovery first. |
| `include_links` | bool | true | Allow the HTML link fallback. |
| `same_domain` | bool | true | Keep URLs on the same domain only. |
| `exclude_patterns` | string[] | - | Regexes of URLs to drop. |
| `rank` | bool | false | Score each URL and return the important ones first. Costs one scored pass. |

**Returns** the base domain, the source type (`sitemap` or `links`), the total
count, and an array of discovered URLs with metadata.

**Failure modes**: sites without a sitemap and with heavy JS navigation return
few URLs. `rank=true` is worth the extra pass before deep-fetching a large
site.

---

## `pdf_extract`

Read PDFs, text layer first, OCR fallback for scanned documents.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `input_path` | string[] | required | File paths or URLs, `http`, `https` or `file`. |
| `format` | enum | `markdown` | `markdown`, `json`, `html`, or a comma combination. |
| `password` | string | - | Password for protected files. |
| `pages` | string | - | Page range such as `1-5,8,10-12`. |
| `hybrid` | enum | `""` | Force the OCR fallback (`docling-fast`). |
| `force_ocr` | bool | false | Shortcut for the OCR fallback. |

**Returns** the extracted document in the requested format.

**Failure modes**: the OCR fallback is CPU-heavy and takes seconds per page.
Use `pages` to bound it.

---

## `ping`

Connectivity check. No parameters. Use it once at the start of a session if
searches are failing, not on every call.

---

## `browser_session`

Persistent browser tab reused across calls. Needs a Chromium-based browser with
`--remote-debugging-port`. Without a session, every `browser_action` call gets a
fresh tab that is closed at the end of the call, so state does not survive.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `action` | enum | `list` | `create`, `list`, `info`, `close`. |
| `session_id` | string | - | Required for `info`/`close`. Omit from `close` to close every session. |
| `label` | string | - | Human label folded into the generated id, e.g. `login`. |
| `url` | string | - | Optional page to open in the new session. |

**Returns** for `create`: `session_id`, `label`, `url`, `tabs` (1). For `list`:
`count`, `sessions[]` (each with `session_id`, `label`, `url`, `age_seconds`,
`idle_seconds`, optionally `current_url`), `stale_on_disk[]`, `cap`. For `info`:
the same fields plus `live`. For `close`: the closed id or `closed_count`.

**Failure modes**

- `action=create` with no CDP browser reachable returns `success:false` with
  `error`, `fix` (start Chromium with `--remote-debugging-port=9222`) and
  `call: doctor()`.
- `action=info`/`close` without `session_id` errors (`session_id is required for
  action=info`).
- `action=close` with an unknown id returns `success:false` and
  `unknown session_id`.
- Sessions are capped at 8. The least recently used is evicted when the cap is
  hit; a closed tab is tried once for re-attach, then fails honestly.
- Sessions are owned by this process and vanish on restart.

---

## `fetch_many`

Fetch several URLs in one call: dedups, caps concurrency, honours robots.txt,
shares the cache. Returns per-URL success/status/content plus counts.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `urls` | string[] | required | URLs to fetch (may be a single string of comma/newline-separated URLs). |
| `max_concurrent` | int | 3 | Parallel fetches, 1-8. |
| `max_chars` | int | 5000 | Characters per URL. |
| `focus` | string | - | Keep only content relevant to this query. |
| `respect_robots` | bool | true | Honour robots.txt per URL. |
| `cache_ttl` | int | 3600 | Shared cache TTL in seconds. |

**Returns** `requested`, `deduped` (count dropped by dedup), `attempted`,
`succeeded`, `failed`, `results[]` (each with `url`, `success`, `status`,
`title`, `content`, `chars`, `final_url`, optionally `error`, `method`,
`truncated`, `blocked_by_robots`), `truncated` (true when the 50-URL batch cap
was hit), and `note`.

**Failure modes**

- Empty `urls` returns `success:false`, `urls must not be empty`.
- More than 50 unique URLs: the excess are dropped and `truncated:true` with a
  note naming the batch cap. Call again with the rest.
- A URL blocked by robots.txt returns `blocked_by_robots:true` with
  `error: Disallowed by robots.txt`.
- SSRF-blocked URLs return `errorKind: permanent`.

---

## `crawl`

Breadth-first crawl with hard caps: per-page cap, depth cap, robots.txt, dedup,
concurrency limit. Returns each page's title and trimmed content plus a
`stop_reason`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `start_url` | string | required | Where to start. |
| `max_depth` | int | 1 | Link hops from start, 0-5. |
| `max_urls` | int | 20 | Hard page cap, 1-100. |
| `same_domain` | bool | true | Stay on the start domain. |
| `include_patterns` | string[] | - | Only URLs containing one of these substrings. |
| `exclude_patterns` | string[] | - | Drop URLs containing any of these substrings. |
| `concurrency` | int | 2 | Parallel fetches, capped at 5. |
| `respect_robots` | bool | true | Honour robots.txt. |
| `max_chars` | int | 4000 | Content kept per page. |

**Returns** `start_url`, `pages_crawled`, `pages_succeeded`, `discovered`,
`max_depth` (the clamped cap), `stop_reason`, `truncated` (true unless
`stop_reason` is `completed`), `pages[]` (each with `url`, `depth`, `success`,
`status`, `title`, `chars`, `content`, optionally `error`).

**Failure modes**

- Empty `start_url` returns `success:false`, `start_url is required`.
- `stop_reason` names the cap that stopped the crawl, e.g.
  `max_urls cap (20) reached`. Use it to tell "exhausted" from "truncated".
- `max_urls` is clamped to 100 and `max_depth` to 5 regardless of input.
- Pages disallowed by robots.txt are returned in `pages[]` with an error rather
  than silently skipped.

---

## `extract_links`

Every link on a page with anchor text, title and rel. Resolves relative hrefs,
drops `javascript:`/`mailto:`, dedups, can stay on one domain.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Page to read. |
| `same_domain` | bool | true | Keep links on the start domain only. |
| `max_links` | int | 500 | Cap on returned links. |
| `include_text` | bool | true | Include anchor text, title and rel. |

**Returns** `url`, `count`, `links[]` (each with `url`, and when
`include_text` is true `text`, `title`, `rel`), `truncated` (true when the
page HTML was truncated or `max_links` was reached), `note`.

**Failure modes**

- Empty `url` returns `success:false`, `url is required`.
- HTML parse failure returns `errorKind: permanent`.
- SSRF-blocked URLs return `errorKind: permanent`.

---

## `extract_table`

Pull HTML tables into JSON, CSV or markdown. Reports `tables_found` so you can
pick one by index, and marks `truncated` when `max_rows` is hit.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Page to read. |
| `selector` | string | - | CSS selector narrowing which tables are considered. |
| `fmt` | enum | `json` | `json`, `csv`, `markdown`. |
| `index` | int | 0 | 0-based index among matched tables. |
| `max_rows` | int | 5000 | Cap on returned rows. |

**Returns** `url`, `tables_found`, `table_index`, `format`, `rows`, `cols`,
`truncated`, `data` (rows as a list of string arrays for `json`, a CSV string
for `csv`, a markdown table for `markdown`), and `note` when truncated.

**Failure modes**

- Empty `url` returns `success:false`, `url is required`.
- No `<table>` found returns `errorKind: permanent` with
  `fix: Try selector='table.some-class' or use extract(css) instead`.
- A table with no rows returns `errorKind: permanent`.
- `index` is clamped to the last available table.

---

## `download`

Save a URL to disk and return the local path, byte count, sha256 and content
type. Writes only inside `dest_dir`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | URL to download. |
| `dest_dir` | string | `~/.cache/websearch/downloads` | Directory to write into. |
| `filename` | string | - | Desired filename; sanitised and given an extension from the content type if omitted. |
| `max_bytes` | int | 104857600 | Byte cap on the transfer (100 MB). |

**Returns** `url`, `path`, `bytes`, `sha256`, `content_type`, `truncated`,
and `note` (when truncated, states the file on disk is incomplete).

**Failure modes**

- Empty `url` returns `success:false`, `url is required`.
- SSRF-blocked URLs return `errorKind: permanent`.
- A write failure returns `errorKind: permanent` with
  `fix: Check dest_dir is writable and has space`.
- Path traversal in `filename` is refused (`refusing to write outside dest_dir`).
- When `truncated` is true the file on disk is incomplete: raise `max_bytes` or
  accept the partial file.

---

## `diff_page`

Compare the live page against the cached snapshot. Returns `changed`,
`old_hash`, `new_hash`, and the added/removed lines.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `url` | string | required | Page to compare. |
| `extraction_type` | string | `markdown` | Extraction type of the cached snapshot to compare against. |

**Returns** on the first call for a URL: `changed: null`, `had_previous: false`,
`reason: no previous snapshot cached; call fetch first, then diff again later`.
On later calls: `changed` (bool), `had_previous: true`, `old_hash`, `new_hash`,
`previous_fetched_at`, `added_count`, `removed_count`, `added[]`,
`removed[]` (each capped at 200 lines).

**Failure modes**

- Empty `url` returns `success:false`, `url is required`.
- A failed fetch during comparison returns `errorKind: transient`.
- `had_previous:false` is not an error: fetch the page once, then diff later.

## `form_fill_submit`

Fill several form fields, click submit, and optionally read the result, in one
call. Needs a Chromium-based browser with `--remote-debugging-port`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `fields` | object[] | required | `[{selector, value}]`; add `action: "click"` for checkboxes and radios. |
| `session_id` | string | - | Reuse a persistent tab. Omitted, a temporary session is created and closed. |
| `url` | string | - | Page to open first. |
| `submit_selector` | string | - | Submit control. Omit to fill without submitting. |
| `wait_state` | enum | `networkidle` | `domcontentloaded`, `load`, `networkidle`. |
| `read_selector` | string | - | Read this element after submitting; empty reads the whole page. |
| `timeout` | number | 20 | Per-step timeout in seconds. |

**Returns** `filled[]` (each with `selector`, `ok`, and `value_verified` plus
`value_read_back` when a typed value did not match), `submitted`, `effect`,
`final_url`, and `result`. `effect` is `navigated`, `content_changed` or `none`.

**Failure modes**

- Selector matches nothing -> `element not found`, and the form is NOT submitted.
- Typed value does not read back -> refuses to submit and reports what it read.
- Submit control missing -> `submit control not found`; fields stay filled in the session.
- `effect: none` -> it submitted but nothing changed, usually validation or a JS-only form.

---

## `paginate`

Click a next control repeatedly and collect a value per page. Needs a
Chromium-based browser with `--remote-debugging-port`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `next_selector` | string | required | CSS selector for the next-page control. |
| `session_id` | string | - | Reuse a persistent tab. |
| `url` | string | - | Page to open first. |
| `max_pages` | int | 5 | Hard page cap (1-25). |
| `read_selector` | string | - | What to collect per page; empty reads the whole page. |
| `wait_state` | enum | `networkidle` | Load milestone to wait for after each click. |
| `wait_ms` | int | 600 | Pause after each navigation. |
| `stop_when_unchanged` | bool | true | Stop when URL and content both fail to change. |
| `timeout` | number | 20 | Per-step timeout in seconds. |

**Returns** `pages[]` (each with `page`, `url`, `found`, `value`),
`page_count`, `stop_reason`, `truncated`.

**Failure modes**

- Next control missing -> `next control not found`, and it says no further pages were read.
- Click accepted but nothing changed -> `next control had no effect`.
- Cap reached -> `max_pages cap (N) reached` with `truncated: true`.
