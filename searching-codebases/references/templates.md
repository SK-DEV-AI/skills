# Output templates

Four concrete shapes. Pick the smallest one that answers the question. Never
pad a signature answer into a report.

---

## Template 1 - API answer

For "how do I use X", "what are the options for Y", "does Z accept a timeout".

```
In `<package> <version>`, <the answer, in one or two sentences>.

```<language>
<the quoted signature, default value, or branch of logic>
```

(source: `<path>`, `<package> <version>`)

<One or two sentences on the practical consequence, if it is not obvious
from the signature.>
```

Rules:

- The version appears in the first line. Not in a footnote.
- The signature is quoted, not paraphrased.
- The source line names the file and the version.
- If the read failed, use Template 1b, not a guess.

**Example**

> In `httpx 0.27.0`, the `Client` constructor takes `timeout` as a
> keyword-only argument and it applies to every request the client makes:
>
> ```python
> def __init__(
>     self,
>     *,
>     ...
>     timeout: TimeoutTypes | None = None,
> ) -> None:
> ```
>
> (source: `httpx/_client.py`, `httpx 0.27.0`)
>
> `None` means the client falls back to the library default of 5 seconds for
> connect and 5 seconds for read, so passing an explicit value is usually
> what you want behind a slow proxy.

---

## Template 1b - API answer, read failed

For when the source could not be read. This template exists so the failure is
never papered over.

```
I could not read the source of `<package>` at `<version>`, so I cannot give
you the signature from source.

What I tried:
- `<tool and scope, e.g. code_read(spec="pypi:foo@1.2.3", path="foo/core.py")>` -> `<what came back>`
- `<second attempt>` -> `<what came back>`

The closest thing I found:
- <link or note, clearly labelled as a different version or a different source>

<The concrete next step, e.g. "run `python -c "import foo, inspect;
print(inspect.signature(foo.Client))` in your environment".>
```

---

## Template 2 - Version comparison

For "what changed between X and Y", "can I upgrade", "is v2 different from v3".

```
<One-line bottom line: is it a safe upgrade, a breaking change, or a
behaviour change to watch.>

| Aspect | `<old version>` | `<new version>` | Changed? |
|---|---|---|---|
| <aspect> | <value> | <value> | yes / no / removed / added |

<Breaking changes, if any, with the file and line each came from.>

Sources:
- `<package> <old version>`, `<path>`
- `<package> <new version>`, `<path>`
- `<package> <changelog entry>`
```

**Example**

> This is a breaking change: `verify` was removed from the client
> constructor in `httpx 0.28.0`.

| Aspect | `httpx 0.27.0` | `httpx 0.28.0` | Changed? |
|---|---|---|---|
| `Client(verify=...)` | present | removed | removed |
| `verify` kwarg on `request()` | present | removed | removed |
| `app` argument | present | present | no |
| `follow_redirects` default | `False` | `False` | no |

Breaking changes:
- `verify` removed from `Client.__init__` (`httpx/_client.py`, `httpx 0.28.0`)
- `verify` removed from `Client.request` (`httpx/_client.py`, `httpx 0.28.0`)

---

## Template 3 - Security advisory

For "is this package vulnerable", "should I bump this version".

```
## `<package> <version>`

<Verdict in one line: N known advisories affecting this version, or none
found in the databases queried.>

| Advisory | Severity | Fixed in | Summary |
|---|---|---|---|
| `<GHSA-… / CVE-…>` | <severity> | <version or "unfixed"> | <one line> |

<What the user should do, in one line.>

Database: <Sonatype / OSV.dev> (a fallback means the primary database was
unavailable).
```

Rules:

- Say which database answered. A scan that fell back to OSV.dev is still an
  answer, but the reader deserves to know.
- "None found in the databases queried" is a valid verdict. Never write "this
  package is safe" as an absolute.
- Give the fixed version so the user can act.

---

## Template 4 - Codebase orientation

For "what is this repo", "how does X work", "where is Y defined", for a
repository the user has not read.

```
## `<owner/repo>`

<What it is, one or two sentences, and the language and stack.>

### Layout

- `<path>` - <one line on what lives there>

### Entry points

- `<path:symbol>` - <what it does>

### Answer

<The specific thing the user asked, with the file and line.>
```

**Example**

> ## `tiangolo/typer`
>
> A Python CLI framework built on Click. The package index exposes 6 modules
> under `typer/`.
>
> ### Layout
>
> - `typer/main.py` - the `Typer` class and the decorator that turns a
>   function into a CLI command
> - `typer/models.py` - `ParameterInfo`, the option and argument model
> - `typer/cli.py` - the Click command construction
>
> ### Entry points
>
> - `typer/main.py:Typer` - the app object
> - `typer/main.py:Typer.command` - the decorator
>
> ### Answer
>
> The decorator that turns a function into a CLI command is
> `typer.command` in `typer/main.py`, which builds a `CommandInfo` and
> registers it with the `Typer` instance. It is exported from
> `typer/__init__.py` as `typer.command`.

---

## Template 5 - Result table (machine-generated)

The bundled helper produces this. Use it when a search returned many results
and the agent needs a compact, deduplicated view before deciding what to read.

```
python3 scripts/normalize_results.py --spec "pypi:httpx@0.27.0" < results.json
```

Output:

```
## Results (7 shown, 7 total)

| # | File | Score | Notes |
|---|---|---|---|
| 1 | `httpx/_client.py` | 0.92 | definition |
| 2 | `httpx/_api.py` | 0.78 | definition |
| 3 | `httpx/_config.py` | 0.41 | |
| 4 | `httpx/_models.py` | 0.33 | |
| 5 | `httpx/_urls.py` | 0.18 | |
| 6 | `httpx/_exceptions.py` | 0.12 | |
| 7 | `httpx/_transports/default.py` | 0.09 | |

Duplicate paths removed: 1
```

The deduped, scored table is the point: it lets the agent pick the two files
worth reading out of forty, instead of reading all of them.
