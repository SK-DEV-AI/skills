#!/usr/bin/env python3
"""format_citations.py - turn raw websearch results into a numbered Markdown
source list plus a claim-to-source map.

Purpose
-------
An agent that answers from live search has a pile of raw result objects and
has to turn them into a numbered, citable source list. Doing that by hand
invites three errors: renumbering that does not match the inline `[N]`
markers, duplicated URLs appearing twice, and source entries with no record
of *which claim* they support.

This script does the mechanical part deterministically. Its output (and only
its output) enters the agent's context.

Inputs
------
JSON on stdin. Accepted shapes:

  1. A JSON array of result objects:
       [{"title": "...", "url": "...", "snippet": "...", "claims": ["..."]}, ...]
  2. A JSON object with a "results" (or "sources", "hits", "items") array
     holding the same objects.
  3. A JSON object mapping URLs to result objects or to a claim string.

Per-result fields understood (all optional except url):
  url            the source URL (required)
  title          display title
  snippet        short text; the claim label is derived from it when no
                 explicit claim is given
  source         engine or site name
  claims         list of strings, the claims this source supports
  relevance_score / score  numeric, used for ordering when no explicit
                 order is given
  published      date string, appended to the entry when present

Output
------
Markdown on stdout:

  ## Sources
  1. Title - https://example.com/page (supports: the claim)
  ...
  ## Claim map
  - the claim -> [1] [2]

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
run: a partial source list with warnings is more useful than no output.
"""

import argparse
import json
import re
import sys
from urllib.parse import urlsplit, urlunsplit

# A URL fragment or query string rarely identifies a different document, but
# tracking parameters do. We strip the obvious tracking keys before dedup so
# the same page from two engines is only listed once.
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid",
}


def eprint(*args):
    """Print a diagnostic to stderr."""
    print(*args, file=sys.stderr)


def normalize_url(url):
    """Return a comparable form of a URL: lowercase host, no fragment, no
    tracking parameters, no trailing slash on the path. Used only for
    duplicate detection, never for display."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()

    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    query_parts = []
    for pair in parts.query.split("&"):
        if not pair:
            continue
        key = pair.split("=", 1)[0]
        if key.lower() in TRACKING_PARAMS:
            continue
        query_parts.append(pair)

    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    return urlunsplit((parts.scheme.lower() or "https", netloc, path,
                       "&".join(query_parts), ""))


def first_sentence(text, limit=140):
    """Return a short claim label derived from a snippet.

    The label is the snippet's first sentence, trimmed to a readable length.
    It is a description of what the source says, not a paraphrase of it."""
    if not text:
        return ""
    text = " ".join(str(text).split())
    match = re.split(r"(?<=[.!?])\s", text, maxsplit=1)
    sentence = match[0] if match else text
    if len(sentence) > limit:
        sentence = sentence[: limit - 1].rstrip() + "..."
    return sentence


def coerce_results(payload):
    """Normalise any accepted input shape into a list of result dicts.

    Returns (results, notes). `notes` is a list of human-readable warnings
    about entries that had to be dropped or reshaped."""
    notes = []

    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = None
        for key in ("results", "sources", "hits", "items", "data", "urls"):
            value = payload.get(key)
            if isinstance(value, list):
                raw = value
                break
        if raw is None:
            # Shape 3: {url: {...}} or {url: "claim string"}
            raw = []
            for key, value in payload.items():
                if isinstance(value, dict):
                    entry = dict(value)
                    entry.setdefault("url", key)
                    raw.append(entry)
                elif isinstance(value, str):
                    raw.append({"url": key, "claims": [value]})
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
            entry = {"url": entry}
        if not isinstance(entry, dict):
            notes.append("skipped entry %d: not an object" % index)
            continue

        url = entry.get("url") or entry.get("link") or entry.get("href")
        if not url or not isinstance(url, str):
            notes.append("skipped entry %d: no url" % index)
            continue

        claims = entry.get("claims")
        if isinstance(claims, str):
            claims = [claims]
        elif not isinstance(claims, list):
            claims = []
        claims = [str(c).strip() for c in claims if str(c).strip()]

        if not claims:
            label = first_sentence(entry.get("snippet") or entry.get("text")
                                   or entry.get("description") or "")
            if label:
                claims = [label]
            else:
                title = str(entry.get("title") or "").strip()
                claims = [title] if title else ["source"]

        results.append({
            "url": url.strip(),
            "title": str(entry.get("title") or "").strip(),
            "snippet": str(entry.get("snippet") or entry.get("text") or "").strip(),
            "source": str(entry.get("source") or entry.get("engine") or "").strip(),
            "published": str(entry.get("published") or entry.get("date")
                             or "").strip(),
            "score": entry.get("relevance_score", entry.get("score")),
            "claims": claims,
        })

    return results, notes


def order_results(results):
    """Order results.

    Explicit ordering is respected when the caller supplied an `order` field
    or when the input was already an ordered array and no numeric score was
    given. Otherwise results with a numeric score are sorted by descending
    score, and results without one keep their input position at the end.

    The function is deterministic: equal scores keep their input order."""
    indexed = list(enumerate(results))
    has_score = any(isinstance(r.get("score"), (int, float))
                    and not isinstance(r.get("score"), bool)
                    for _, r in indexed)
    if not has_score:
        return results

    def key(item):
        index, result = item
        score = result.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return (1, 0.0, index)
        return (0, -float(score), index)

    indexed.sort(key=key)
    return [result for _, result in indexed]


def dedupe(results):
    """Drop entries whose URL matches an earlier entry (after normalisation).

    When a duplicate is dropped, its claims are merged into the entry that
    survived, so no claim is lost. Returns (kept, dropped_count)."""
    kept = []
    seen = {}
    dropped = 0
    for result in results:
        key = normalize_url(result["url"])
        if key and key in seen:
            dropped += 1
            existing = kept[seen[key]]
            for claim in result["claims"]:
                if claim not in existing["claims"]:
                    existing["claims"].append(claim)
            continue
        if key:
            seen[key] = len(kept)
        kept.append(result)
    return kept, dropped


def render(results, query, max_sources):
    """Render the numbered source list and the claim map as Markdown."""
    lines = []
    lines.append("## Sources")
    lines.append("")

    number_for_claim = {}
    for number, result in enumerate(results, start=1):
        title = result["title"] or result["url"]
        supports = "; ".join(result["claims"])
        entry = "%d. %s - %s" % (number, title, result["url"])
        detail = "supports: %s" % supports
        if result["source"]:
            detail = "[%s] %s" % (result["source"], detail)
        if result["published"]:
            detail = "%s (published: %s)" % (detail, result["published"])
        lines.append("%s (%s)" % (entry, detail))

        for claim in result["claims"]:
            number_for_claim.setdefault(claim, []).append(number)

    lines.append("")
    lines.append("## Claim map")
    lines.append("")
    if query:
        lines.append("- research question -> %s" % query)
    for claim, numbers in number_for_claim.items():
        markers = " ".join("[%d]" % n for n in numbers)
        lines.append("- %s -> %s" % (claim, markers))

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
        prog="format_citations.py",
        description="Format raw websearch results as a numbered Markdown "
                    "source list with a claim-to-source map.",
        epilog="Reads JSON from stdin unless --input is given. Writes "
               "Markdown to stdout and diagnostics to stderr.")
    parser.add_argument("--input", "-i", default="-",
                        help="read the JSON payload from this file "
                             "(default: stdin)")
    parser.add_argument("--query", "-q", default="",
                        help="the research question, included at the top of "
                             "the claim map")
    parser.add_argument("--max-sources", "-n", type=int, default=25,
                        help="maximum number of sources to list (default: 25)")
    parser.add_argument("--no-claim-map", action="store_true",
                        help="emit only the numbered source list")
    args = parser.parse_args(argv)

    if args.max_sources < 1:
        eprint("error: --max-sources must be at least 1")
        sys.exit(1)

    payload = load_payload(args.input)
    results, notes = coerce_results(payload)
    for note in notes:
        eprint("warning: %s" % note)

    if not results:
        eprint("error: no usable results found in the input")
        sys.exit(2)

    results = order_results(results)
    results, dropped = dedupe(results)
    if dropped:
        eprint("note: dropped %d duplicate URL(s), claims merged" % dropped)

    if len(results) > args.max_sources:
        eprint("note: truncated from %d to %d sources"
               % (len(results), args.max_sources))
        results = results[: args.max_sources]

    if args.no_claim_map:
        # The claim map is the useful half; without it, still emit the list.
        lines = ["## Sources", ""]
        for number, result in enumerate(results, start=1):
            title = result["title"] or result["url"]
            supports = "; ".join(result["claims"])
            lines.append("%d. %s - %s (supports: %s)"
                         % (number, title, result["url"], supports))
        print("\n".join(lines))
        return 0

    print(render(results, args.query, args.max_sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
