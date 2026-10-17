import logging

import pytest

from github_actions_logger import Logger, is_github_actions


@pytest.fixture
def ci_logger() -> Logger:
    return Logger("ci", in_ci=True)


@pytest.fixture
def local_logger() -> Logger:
    return Logger("local", in_ci=False)


class TestDetection:
    def test_detects_github_actions(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert is_github_actions() is True
        assert Logger("x")._in_ci is True

    @pytest.mark.parametrize("value", [None, "", "false", "1"])
    def test_not_github_actions(self, monkeypatch, value):
        if value is None:
            monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        else:
            monkeypatch.setenv("GITHUB_ACTIONS", value)
        assert is_github_actions() is False
        assert Logger("x")._in_ci is False

    def test_in_ci_overrides_environment(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert Logger("x", in_ci=False)._in_ci is False
        monkeypatch.delenv("GITHUB_ACTIONS")
        assert Logger("x", in_ci=True)._in_ci is True

    def test_detected_once_at_init(self, monkeypatch):
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        logger = Logger("x")
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert logger._in_ci is False


class TestCommands:
    @pytest.mark.parametrize(
        ("method", "command"),
        [
            ("debug", "debug"),
            ("info", "notice"),
            ("warning", "warning"),
            ("error", "error"),
            ("critical", "error"),
        ],
    )
    def test_level_mapping(self, ci_logger, capsys, method, command):
        getattr(ci_logger, method)("hello")
        assert capsys.readouterr().out == f"::{command}::hello\n"

    def test_args_are_formatted(self, ci_logger, capsys):
        ci_logger.info("%s has %d items", "list", 3)
        assert capsys.readouterr().out == "::notice::list has 3 items\n"

    def test_message_escaping(self, ci_logger, capsys):
        ci_logger.info("100%\r\nnext")
        assert capsys.readouterr().out == "::notice::100%25%0D%0Anext\n"

    def test_non_string_message(self, ci_logger, capsys):
        ci_logger.info(42)
        assert capsys.readouterr().out == "::notice::42\n"

    def test_exception_includes_traceback(self, ci_logger, capsys):
        try:
            raise ValueError("boom")
        except ValueError:
            ci_logger.exception("failed")
        out = capsys.readouterr().out
        assert out.startswith("::error::failed%0A")
        assert "ValueError: boom" in out
        assert out.count("\n") == 1  # single command line

    def test_exc_info_instance(self, ci_logger, capsys):
        ci_logger.error("failed", exc_info=KeyError("k"))
        assert "KeyError" in capsys.readouterr().out

    def test_exc_info_without_active_exception(self, ci_logger, capsys):
        ci_logger.error("failed", exc_info=True)
        assert capsys.readouterr().out == "::error::failed\n"


class TestAnnotations:
    def test_all_properties(self, ci_logger, capsys):
        ci_logger.warning(
            "msg",
            extra={
                "title": "T",
                "file": "src/app.py",
                "line": 1,
                "end_line": 2,
                "col": 3,
                "end_column": 4,
            },
        )
        assert capsys.readouterr().out == (
            "::warning title=T,file=src/app.py,line=1,endLine=2,col=3,endColumn=4::msg\n"
        )

    def test_property_escaping(self, ci_logger, capsys):
        ci_logger.error("m", extra={"title": "a, b: c\n%", "file": r"C:\x.py"})
        assert capsys.readouterr().out == (
            "::error title=a%2C b%3A c%0A%25,file=C%3A\\x.py::m\n"
        )

    def test_none_and_unknown_keys_ignored(self, ci_logger, capsys):
        ci_logger.info("m", extra={"title": None, "line": 5, "custom": "x"})
        assert capsys.readouterr().out == "::notice line=5::m\n"

    def test_empty_extra(self, ci_logger, capsys):
        ci_logger.info("m", extra={})
        assert capsys.readouterr().out == "::notice::m\n"

    def test_debug_ignores_properties(self, ci_logger, capsys):
        ci_logger.debug("m", extra={"title": "T", "file": "f.py"})
        assert capsys.readouterr().out == "::debug::m\n"


class TestGroups:
    def test_group_wraps_output(self, ci_logger, capsys):
        with ci_logger.group("Build"):
            ci_logger.info("inside")
        assert capsys.readouterr().out == (
            "::group::Build\n::notice::inside\n::endgroup::\n"
        )

    def test_title_escaping(self, ci_logger, capsys):
        with ci_logger.group("100%\nnext"):
            pass
        assert capsys.readouterr().out == "::group::100%25%0Anext\n::endgroup::\n"

    def test_endgroup_on_exception(self, ci_logger, capsys):
        with pytest.raises(ValueError), ci_logger.group("Build"):
            raise ValueError("boom")
        assert capsys.readouterr().out == "::group::Build\n::endgroup::\n"

    def test_as_target(self, ci_logger):
        with ci_logger.group("Build") as group:
            assert group.title == "Build"

    def test_noop_outside_ci(self, local_logger, capsys):
        with local_logger.group("Build"):
            pass
        assert capsys.readouterr().out == ""


class TestLocal:
    @pytest.mark.parametrize(
        ("method", "level"),
        [
            ("debug", logging.DEBUG),
            ("info", logging.INFO),
            ("warning", logging.WARNING),
            ("error", logging.ERROR),
            ("critical", logging.CRITICAL),
        ],
    )
    def test_uses_standard_logging(self, local_logger, caplog, capsys, method, level):
        local_logger.setLevel(logging.DEBUG)
        local_logger.addHandler(caplog.handler)
        getattr(local_logger, method)("hello %s", "world")
        assert capsys.readouterr().out == ""
        assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
            (level, "hello world")
        ]

    def test_respects_level(self, local_logger, caplog):
        local_logger.setLevel(logging.ERROR)
        local_logger.addHandler(caplog.handler)
        local_logger.info("hidden")
        assert caplog.records == []

    def test_extra_becomes_record_attributes(self, local_logger, caplog):
        local_logger.addHandler(caplog.handler)
        local_logger.warning("m", extra={"title": "T", "file": "f.py", "line": 7})
        record = caplog.records[0]
        assert (record.title, record.file, record.line) == ("T", "f.py", 7)
