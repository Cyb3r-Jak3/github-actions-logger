import logging
import os
import sys
import traceback


def is_github_actions() -> bool:
    """Return True when running inside a GitHub Actions workflow."""
    return os.environ.get("GITHUB_ACTIONS") == "true"


def _escape_data(message: str) -> str:
    """Escape a message as required by workflow commands."""
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: object) -> str:
    """Escape an annotation property value as required by workflow commands."""
    return _escape_data(str(value)).replace(":", "%3A").replace(",", "%2C")


# `extra` key -> workflow command property name
_ANNOTATION_PROPERTIES = {
    "title": "title",
    "file": "file",
    "line": "line",
    "end_line": "endLine",
    "col": "col",
    "end_column": "endColumn",
}


def _exc_text(exc_info: object) -> str:
    """Format an `exc_info` argument the way `logging` accepts it."""
    if exc_info is True:
        exc_info = sys.exc_info()
    elif isinstance(exc_info, BaseException):
        exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
    if not isinstance(exc_info, tuple) or exc_info[0] is None:
        return ""
    return "".join(traceback.format_exception(*exc_info)).rstrip("\n")


class Group:
    """Context manager that wraps output in a collapsible log group.

    Emits `::group::{title}` on entry and `::endgroup::` on exit. Does nothing
    when not running in CI.
    """

    def __init__(self, title: str, in_ci: bool) -> None:
        self.title = title
        self._in_ci = in_ci

    def __enter__(self) -> "Group":
        if self._in_ci:
            sys.stdout.write(f"::group::{_escape_data(self.title)}\n")
            sys.stdout.flush()
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._in_ci:
            sys.stdout.write("::endgroup::\n")
            sys.stdout.flush()


class Logger(logging.Logger):
    """Logger that emits GitHub Actions workflow commands when running in CI.

    `debug` -> `::debug::`, `info` -> `::notice::`, `warning` -> `::warning::`,
    `error`/`critical`/`exception` -> `::error::`. Outside CI, standard logging is used.

    Annotation properties can be passed via `extra` (ignored for `debug`):
    `title`, `file`, `line`, `end_line`, `col` and `end_column`.
    """

    def __init__(self, name: str, in_ci: bool | None = None) -> None:
        super().__init__(name)
        self._in_ci = is_github_actions() if in_ci is None else in_ci

    def _command(self, command: str, msg: object, args: tuple, kwargs: dict) -> None:
        message = str(msg) % args if args else str(msg)
        if kwargs.get("exc_info"):
            text = _exc_text(kwargs["exc_info"])
            if text:
                message = f"{message}\n{text}"
        properties = ""
        extra = kwargs.get("extra")
        if command != "debug" and isinstance(extra, dict):
            parts = [
                f"{name}={_escape_property(extra[key])}"
                for key, name in _ANNOTATION_PROPERTIES.items()
                if extra.get(key) is not None
            ]
            if parts:
                properties = " " + ",".join(parts)
        sys.stdout.write(f"::{command}{properties}::{_escape_data(message)}\n")
        sys.stdout.flush()

    def group(self, title: str) -> Group:
        """Return a context manager that wraps output in a collapsible log group."""
        return Group(title, self._in_ci)

    def debug(self, msg: object, *args: object, **kwargs: object) -> None:
        if self._in_ci:
            self._command("debug", msg, args, kwargs)
        else:
            super().debug(msg, *args, **kwargs)  # type: ignore[arg-type]

    def info(self, msg: object, *args: object, **kwargs: object) -> None:
        if self._in_ci:
            self._command("notice", msg, args, kwargs)
        else:
            super().info(msg, *args, **kwargs)  # type: ignore[arg-type]

    def warning(self, msg: object, *args: object, **kwargs: object) -> None:
        if self._in_ci:
            self._command("warning", msg, args, kwargs)
        else:
            super().warning(msg, *args, **kwargs)  # type: ignore[arg-type]

    def error(self, msg: object, *args: object, **kwargs: object) -> None:
        if self._in_ci:
            self._command("error", msg, args, kwargs)
        else:
            super().error(msg, *args, **kwargs)  # type: ignore[arg-type]

    def critical(self, msg: object, *args: object, **kwargs: object) -> None:
        if self._in_ci:
            self._command("error", msg, args, kwargs)
        else:
            super().critical(msg, *args, **kwargs)  # type: ignore[arg-type]
