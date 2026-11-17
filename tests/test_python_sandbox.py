import pytest

from core.agents import python_exec


def run(code):
    return python_exec.run_code(code)


def test_simple_print():
    result = run("print('hello', 1 + 2)")
    assert result["ok"]
    assert result["stdout"].strip() == "hello 3"


def test_trailing_expression_is_echoed():
    assert run("x = 2\nx ** 100")["stdout"].strip() == str(2 ** 100)


def test_allowed_imports_and_classes():
    code = """
import math, statistics
from collections import Counter
from math import *
class Acc:
    def __init__(self):
        self._total = 0
    def add(self, n):
        self._total += n
        return self
    def total(self):
        return self._total
print(math.sqrt(16), statistics.mean([1, 2, 3]), Counter('aab')['a'], floor(2.7), Acc().add(5).total())
"""
    result = run(code)
    assert result["ok"], result["stderr"]
    assert result["stdout"].strip() == "4.0 2 2 2 5"


def test_runtime_error_shows_user_traceback():
    result = run("def f():\n    return 1 / 0\nf()")
    assert not result["ok"]
    assert "ZeroDivisionError" in result["stderr"]
    assert "sandbox_runner" not in result["stderr"]


def test_syntax_error():
    result = run("print(")
    assert not result["ok"]
    assert "SyntaxError" in result["stderr"]


def test_timeout(monkeypatch):
    monkeypatch.setattr(python_exec.config, "PYTHON_TIMEOUT", 2)
    result = run("while True:\n    pass")
    assert result["timed_out"]


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('echo pwned')",
        "import subprocess",
        "from os import system",
        "__import__('os')",
        "open('x.txt', 'w')",
        "eval('1+1')",
        "exec('print(1)')",
        "().__class__.__base__.__subclasses__()",
        "getattr((), '__cla' + 'ss__')",
        "import random\nrandom._os",
        "def g():\n    yield 1\ng().gi_frame.f_globals",
        "'{0.__class__}'.format(1)",
        "globals()",
        "vars()",
    ],
)
def test_escapes_are_blocked(code):
    result = run(code)
    assert not result["ok"]
    assert "pwned" not in result["stdout"]


@pytest.mark.parametrize(
    "code",
    [
        # Runtime-string attribute lookups that the AST check can't see.
        "import operator\noperator.attrgetter('__class__')(1)",
        "from operator import methodcaller\nmethodcaller('__dir__')(1)",
        "import string\nstring.Formatter",
        "getattr(1, '_' + '_class__')",
        # Modules reachable as attributes of allowed modules.
        "import json\njson.decoder",
        "import uuid\nuuid.os",
        "import calendar\ncalendar.sys",
    ],
)
def test_runtime_lookups_are_blocked(code):
    result = run(code)
    assert not result["ok"]
    assert "Error" in result["stderr"]


def test_child_gets_no_secrets(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "secret-value")
    captured = {}
    real_run = python_exec.subprocess.run

    def spy(*args, **kwargs):
        captured.update(kwargs["env"])
        return real_run(*args, **kwargs)

    monkeypatch.setattr(python_exec.subprocess, "run", spy)
    assert run("print('ok')")["ok"]
    assert "GROQ_API_KEY" not in captured


@pytest.mark.parametrize(
    "query,expected",
    [
        ("Execute this Python code:\nx = 1\nprint(x)", "x = 1\nprint(x)"),
        ("run this code: print(2)", "print(2)"),
        ("Please run this:\n```python\nprint('a')\n```", "print('a')"),
        ("print(1)", "print(1)"),
        ("Here is my code\nprint(3)", "print(3)"),
    ],
)
def test_extract_code(query, expected):
    assert python_exec.extract_code(query) == expected


@pytest.mark.parametrize(
    "query,expected",
    [
        ("print('hi')", True),
        ("x = 5\ny = x * 2\nprint(y)", True),
        ("```\n1+1\n```", True),
        ("Execute this Python code: 1+1", True),
        ("what is python?", False),
        ("hello", False),
        ("summarize the video", False),
    ],
)
def test_looks_like_code(query, expected):
    assert python_exec.looks_like_code(query) is expected


def test_handle_rejects_input():
    result = python_exec.handle("s", "x = input('name')")
    assert not result["success"]
    assert "input()" in result["reply"]
