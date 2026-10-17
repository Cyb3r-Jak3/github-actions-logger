# github-actions-logger

A `logging.Logger` subclass that emits [GitHub Actions workflow commands](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands) when running in CI, and behaves like a normal logger everywhere else.

## Installation

```bash
pip install github-actions-logger
```

Or with uv:

```bash
uv add github-actions-logger
```

Requires Python 3.12 or newer.

## Usage

```python
from github_actions_logger import Logger

log = Logger("my-app")

log.debug("Cache key: %s", key)
log.info("Deployed")
log.warning("Deprecated option used")
log.error("Build failed")
```

In GitHub Actions (detected via `GITHUB_ACTIONS=true`) these print:

```text
::debug::Cache key: abc123
::notice::Deployed
::warning::Deprecated option used
::error::Build failed
```

Anywhere else, the calls go through standard `logging`, so handlers, levels and formatters work as usual.

### Level mapping

| Method | Workflow command |
| --- | --- |
| `debug` | `::debug::` |
| `info` | `::notice::` |
| `warning` | `::warning::` |
| `error`, `critical`, `exception` | `::error::` |

`exception()` (or any call with `exc_info`) appends the traceback to the message.

### Annotations

`notice`, `warning` and `error` messages can be attached to a file and line by passing the standard `extra` argument:

```python
log.warning(
    "Unused import",
    extra={"title": "Lint", "file": "src/app.py", "line": 12, "end_line": 12, "col": 1, "end_column": 20},
)
```

```text
::warning title=Lint,file=src/app.py,line=12,endLine=12,col=1,endColumn=20::Unused import
```

| `extra` key | Workflow property |
| --- | --- |
| `title` | `title` |
| `file` | `file` |
| `line` | `line` |
| `end_line` | `endLine` |
| `col` | `col` |
| `end_column` | `endColumn` |

Missing or `None` keys and unrelated keys are ignored, and `debug` ignores them entirely since `::debug::` takes no properties. Outside CI, `extra` becomes attributes on the `LogRecord`, so a formatter can use it (for example `%(file)s:%(line)s`).

### Overriding detection

CI detection happens once, when the logger is created. To force it on or off, pass `in_ci`:

```python
Logger("my-app", in_ci=True)   # always emit workflow commands
Logger("my-app", in_ci=False)  # always use standard logging
```

### Notes

- In CI, messages are written straight to stdout and bypass the logger's level and handlers. GitHub only displays `::debug::` lines when step debug logging is enabled (`ACTIONS_STEP_DEBUG`).
- Create the logger with `Logger(...)` directly. `logging.setLoggerClass(Logger)` plus `logging.getLogger(name)` works, but only passes `name`, so `in_ci` can't be set that way.

## Development

```bash
uv run pytest
```

Runs the tests with a coverage report.
