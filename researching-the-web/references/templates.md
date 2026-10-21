# Output templates

Four concrete shapes. Pick the smallest one that answers the question. Never
pad a quick fact into a brief.

---

## Template 1 - Quick fact

For a single fact, version, date, or definition. Two to four sentences plus
sources.

```
<Direct answer, 1-3 sentences.>

<Optional second sentence of qualification, e.g. the date it was true as of.>

Sources:
1. <Title> - <url> (<what it supports>)
2. <Title> - <url> (<what it supports>)
```

**Example**

> PostgreSQL 17 is the current major release (as of 2026-10-21). It was
> released on 2024-09-26 and is the supported major line [1].
>
> Sources:
> 1. PostgreSQL versioning policy - https://www.postgresql.org/support/versioning/ (release dates, support window)
> 2. PostgreSQL 17 release announcement - https://www.postgresql.org/docs/17/release-17.html (feature list)

---

## Template 2 - Comparison table

For "A versus B", "which should I pick", "what are the options".

```
<One-line recommendation first, with the deciding factor named.>

| Criterion | A | B |
|---|---|---|
| <criterion 1> | <value> | <value> |
| <criterion 2> | <value> | <value> |

<One paragraph on the tradeoff, and who each one suits.>

Sources:
1. <Title> - <url> (<what it supports>)
```

Rules:

- One row per criterion that the user actually cares about. Do not invent rows
  to fill the table.
- A cell that is "not documented" is better than a cell that is a guess.
- Every cell that carries a factual claim needs a source; put the marker in
  the cell.

**Example**

> Pick Postgres if you need extensions and strict SQL, MongoDB if the access
> pattern is document-shaped and you will not need cross-document joins [1][2].

| Criterion | PostgreSQL 17 | MongoDB 8 |
|---|---|---|
| Data model | Relational, typed schema [1] | Document, flexible schema [2] |
| Joins | Full SQL, mature planner [1] | Limited; aggregation pipeline instead [2] |
| Scaling | Vertical first, then partitions [1] | Sharding built in [2] |
| Best for | Multi-entity integrity | Rapidly changing shapes |

---

## Template 3 - Researched brief

For "research X", "give me a briefing on X", "what do I need to know about X".

```
## <Topic>

<Direct answer or bottom line, 2-4 sentences.>

## What was found

- <Finding> [1]
- <Finding> [2]
- <Finding> [3]

## Open questions

- <What could not be confirmed, and why.>

Sources:
1. <Title> - <url> (<what it supports>)
```

Rules:

- "What was found" is a list of findings, each with a citation. Not a summary
  of the source's own structure.
- "Open questions" is not optional. If everything was confirmed, write
  "None. Every claim above is supported by a primary source." If something was
  not confirmed, say exactly what and why. A brief that never admits a gap is
  a brief nobody can trust.
- Keep the whole brief under about 600 words unless the user asked for depth.

---

## Template 4 - Source list (machine-generated)

The bundled helper produces this. Use it when the answer has more than about
five sources, or when the agent wants a consistent numbered list rather than
hand-formatting one.

```
python3 scripts/format_citations.py --query "<the research question>" < results.json
```

Output:

```
## Sources

1. Django release notes - https://www.djangoproject.com/download/ (stable version, security release dates)
2. NVD Django entries - https://nvd.nist.gov/vuln/search/results?q=django (CVE list and fixed versions)

## Claim map

- stable version -> [1]
- known unpatched CVEs -> [1] [2]
```

The claim map is the part that matters: it makes it obvious which claim rests
on which source, so a reader can audit the answer in one pass. A source list
without a claim map is a bookmark list.

---

## Citation list format, for hand-writing

```
Sources:
1. <Title> - <url> (<what this source supports>)
2. <Title> - <url> (<what this source supports>)
```

Inline markers in the body are `[1]`, `[2]`, matching the list.

Two acceptable forms of each entry, both fine:

- `1. Django release notes - https://example.com/notes (stable version)`
- `1. https://example.com/notes (Django release notes, stable version)`

What is not acceptable:

- `1. Django release notes` (no URL, no claim)
- `1. https://example.com/notes` (no claim)
- A bulleted list of bare URLs under a heading called "Sources" with no
  numbering and no inline markers, because then nothing in the body points at
  anything.
