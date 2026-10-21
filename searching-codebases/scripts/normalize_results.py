#!/usr/bin/env python3
"""normalize_results.py - turn a codesearch result payload into a compact,
deduplicated Markdown table.

Purpose
-------
A code search returns many overlapping hits: the same file matched by several
symbols, the same path listed twice by different indexers, results with and
without a score, documentation hits mixed in with code hits. Reading all of
them wastes context and buries the two files actually worth opening.

This script normalises the payload, removes duplicate paths, and prints a
ranked table so the agent can pick what to read next. Its output (and only its
output) enters the agent's context.

Inputs
------
JSON on stdin. Accepted shapes:

  1. A JSON array of result objects.
  2. A JSON object with a "results" (or "files", "hits", "items", "matches",
     "symbols") array holding the same objects.
  3. A JSON object mapping a path to a result object or to a score number.

Per-result fields understood (all optional except one of path/url/file):
  path / file / filename   the file path (preferred key)
  url                       a URL; the path is derived from it
  name / symbol             a symbol name
  kind / type               "function", "class", "method", ...
  score / relevance_score   numeric relevance, used for ordering
  line / line_number        a line number
  doc / documentation       the docstring or doc excerpt
  kind_note / notes         a free-text note

Output
------
Markdown on stdout:

  ## Results (7 shown, 7 total)

  | # | File | Symbol | Score | Notes |
  |---|---|---|---|---|
  | 1 | httpx/_client.py | Client | 0.92 | class |

  Duplicate paths removed: 1

Diagnostics (counts, warnings) go to stderr, never to stdout, so stdout stays
machine-parseable.

Safety
------
This script reads only stdin and the file given on the command line. It
performs NO network access, installs nothing, writes no files, and modifies
nothing on disk. It deliberately does not read ANY environment variable:
credentials for the MCP server are configured by the user, on the user's
machine, and this skill never handles, inspects or prints them.

Exit codes
----------
  0  success
  1  usage error (bad arguments, unreadable input file)
  2  input was not valid JSON, or contained no usable results

Malformed or duplicate entries are reported on stderr and do not fail the
run: a partial table with warnings is more useful than no output.
"""

import argparse
import json
import os
import sys
from urllib.parse import urlsplit

# Keys that may hold the list of results, in priority order.
RESULT_KEYS = ("results", "files", "hits", "items", "matches", "symbols",
               "docs", "data")

# Keys that may hold a file path, in priority order.
PATH_KEYS = ("path", "file", "filename", "filepath", "file_path")

# Keys that may hold a numeric relevance score, in priority order.
SCORE_KEYS = ("score", "relevance_score", "relevance", "rank_score", "weight")


def eprint(*args):
    """Print a diagnostic to stderr."""
    print(*args, file=sys.stderr)


def path_from_url(url):
    """Derive a repository-relative path from a URL.

    Handles the shapes these tools return:
      https://github.com/owner/repo/blob/main/src/a.py
      https://raw.githubusercontent.com/owner/repo/main/src/a.py
      https://cdn.jsdelivr.net/npm/express@4.19.2/lib/express.js
    Returns an empty string when nothing sensible can be derived."""
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""

    path = parts.path or ""

    for marker in ("/blob/", "/tree/", "/raw/"):
        index = path.find(marker)
        if index != -1:
            rest = path[index + len(marker):].lstrip("/")
            segments = rest.split("/")
            # The first segment after /blob/ or /tree/ is the branch or tag
            # reference, not part of the file path. Drop it when there is
            # more than one segment left.
            if len(segments) > 1:
                segments = segments[1:]
            return "/".join(segments)

    # jsDelivr and similar: keep everything after the first path segment that
    # follows the package name, minus the version segment.
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2 and segments[0] in ("npm", "pypi", "crates"):
        return "/".join(segments[2:]) or ""

    return path.lstrip("/")


def first_present(entry, keys):
    """Return the first non-empty value among `keys` in `entry`."""
    for key in keys:
        value = entry.get(key)
        if value not in (None, ""):
            return value
    return None


def coerce_results(payload):
    """Normalise any accepted input shape into a list of result dicts.

    Returns (results, notes). `notes` holds human-readable warnings about
    entries that had to be dropped or reshaped."""
    notes = []

    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = None
        for key in RESULT_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                raw = value
                break
        if raw is None:
            # Shape 3: {path: {...}} or {path: score}
            raw = []
            for key, value in payload.items():
                if isinstance(value, dict):
                    entry = dict(value)
                    entry.setdefault("path", key)
                    raw.append(entry)
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    raw.append({"path": key, "score": value})
                else:
                    notes.append("skipped non-object entry: %r" % (key,))
            if not raw:
                notes.append("input object had no recognisable result list")
                return [], notes
    else:
        notes.append("input was neither a list nor an object")
        return [], notes

    results = []
    for index, entry in enumerate(raw, start=1):
        if isinstance(entry, str):
            entry = {"path": entry}
        if not isinstance(entry, dict):
            notes.append("skipped entry %d: not an object" % index)
            continue

        path = first_present(entry, PATH_KEYS)
        if not path:
            url = entry.get("url")
            if url:
                path = path_from_url(url)
            if not path:
                notes.append("skipped entry %d: no path or url" % index)
                continue
        path = str(path).strip()

        score = first_present(entry, SCORE_KEYS)
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            score = None
        else:
            score = float(score)

        line = first_present(entry, ("line", "line_number", "start_line"))
        if isinstance(line, bool) or not isinstance(line, int):
            line = None

        doc = first_present(entry, ("doc", "documentation", "docstring",
                                    "snippet", "text"))
        note = first_present(entry, ("kind_note", "notes", "note", "kind",
                                     "type"))

        results.append({
            "path": path,
            "symbol": str(first_present(entry, ("name", "symbol",
                                                "symbol_name")) or "").strip(),
            "kind": str(entry.get("kind") or entry.get("type") or "").strip(),
            "score": score,
            "line": line,
            "doc": str(doc).strip() if doc else "",
            "note": str(note).strip() if note else "",
            "url": str(entry.get("url") or "").strip(),
        })

    return results, notes


def order_results(results):
    """Order results by descending score, unscored entries after scored ones.

    Deterministic: entries with equal scores keep their input order, and the
    input order is the order the search tool ranked them in."""
    indexed = list(enumerate(results))

    def key(item):
        index, result = item
        score = result["score"]
        if score is None:
            return (1, 0.0, index)
        return (0, -score, index)

    indexed.sort(key=key)
    return [result for _, result in indexed]


def dedupe(results):
    """Remove entries that point at the same path.

    The first occurrence of a path wins, because results arrive in the
    tool's own relevance order. Later duplicates are dropped, but their
    symbol names and notes are merged into the survivor so no information is
    lost. Returns (kept, dropped_count)."""
    kept = []
    index_of = {}
    dropped = 0

    for result in results:
        key = os.path.normpath(result["path"]) if result["path"] else result["path"]
        if key in index_of:
            dropped += 1
            existing = kept[index_of[key]]
            for field in ("symbol", "kind", "note", "doc"):
                if not existing[field] and result[field]:
                    existing[field] = result[field]
            if existing["score"] is None and result["score"] is not None:
                existing["score"] = result["score"]
            continue
        index_of[key] = len(kept)
        kept.append(result)

    return kept, dropped


def escape_cell(text):
    """Make a value safe to put inside a Markdown table cell."""
    if not text:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def render(results, spec, total, dropped, max_rows):
    """Render the normalised results as a Markdown table."""
    lines = []
    lines.append("## Results (%d shown, %d total)" % (len(results), total))
    lines.append("")
    lines.append("| # | File | Symbol | Score | Notes |")
    lines.append("|---|---|---|---|---|")

    for number, result in enumerate(results, start=1):
        symbol = result["symbol"]
        if symbol and result["line"]:
            symbol = "%s:%d" % (symbol, result["line"])
        notes = result["note"]
        if result["kind"] and result["kind"] != notes:
            notes = ("%s, %s" % (result["kind"], notes)).strip(", ")
        score = "" if result["score"] is None else ("%.2f" % result["score"])
        lines.append("| %d | `%s` | %s | %s | %s |" % (
            number,
            escape_cell(result["path"]),
            escape_cell(symbol),
            score,
            escape_cell(notes),
        ))

    if dropped:
        lines.append("")
        lines.append("Duplicate paths removed: %d" % dropped)
    if spec:
        lines.append("")
        lines.append("Scope: `%s`" % spec)

    return "\n".join(lines)


def load_payload(path):
    """Read the JSON payload from a file path, or from stdin when path is
    '-' or omitted."""
    if path in (None, "-"):
        raw = sys.stdin.read()
    else:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except OSError as exc:
            eprint("error: cannot read %s: %s" % (path, exc))
            sys.exit(1)

    raw = raw.strip()
    if not raw:
        eprint("error: empty input")
        sys.exit(2)

    try:
        return json.loads(raw)
    except ValueError as exc:
        eprint("error: input is not valid JSON: %s" % exc)
        sys.exit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="normalize_results.py",
        description="Normalise a codesearch result payload into a compact, "
                    "deduplicated Markdown table of files and symbols.",
        epilog="Reads JSON from stdin unless --input is given. Writes "
               "Markdown to stdout and diagnostics to stderr.")
    parser.add_argument("--input", "-i", default="-",
                        help="read the JSON payload from this file "
                             "(default: stdin)")
    parser.add_argument("--spec", "-s", default="",
                        help="the package or repository scope the results "
                             "came from, e.g. pypi:httpx@0.27.0")
    parser.add_argument("--max-rows", "-n", type=int, default=30,
                        help="maximum number of rows to print (default: 30)")
    parser.add_argument("--no-dedupe", action="store_true",
                        help="keep duplicate paths")
    args = parser.parse_args(argv)

    if args.max_rows < 1:
        eprint("error: --max-rows must be at least 1")
        sys.exit(1)

    payload = load_payload(args.input)
    results, notes = coerce_results(payload)
    for note in notes:
        eprint("warning: %s" % note)

    if not results:
        eprint("error: no usable results found in the input")
        sys.exit(2)

    total = len(results)
    results = order_results(results)

    dropped = 0
    if not args.no_dedupe:
        results, dropped = dedupe(results)
        if dropped:
            eprint("note: removed %d duplicate path(s), details merged"
                   % dropped)

    if len(results) > args.max_rows:
        eprint("note: truncated from %d to %d rows"
               % (len(results), args.max_rows))
        results = results[: args.max_rows]

    print(render(results, args.spec, total, dropped, args.max_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
