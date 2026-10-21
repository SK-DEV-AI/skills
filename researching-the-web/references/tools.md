# websearch tool reference

Every tool, every parameter, what it returns, and how it fails.

All tool names below are MCP tools on the `websearch` server. In a client that
exposes MCP tools by their fully-qualified name they are called as
`mcp__websearch__<tool>`.

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
| `google_ai_only` | bool | `false` | Skip every other engine and use Google AI Mode only. |
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
