"""Restricted Python executor.

Run as ``python -I sandbox_runner.py`` with user code on stdin, inside a throwaway temp directory,
a minimal environment and a timeout (see python_exec.py). Three layers keep the code contained:

1. validate() rejects, before running, imports outside ALLOWED_MODULES, dunder/private attribute
   access and dangerous builtins (eval, exec, open, ...).
2. The code runs with a whitelist of builtins; imported modules are wrapped in proxies that hide
   private attributes and any submodule that isn't itself allowed (e.g. ``typing.sys``).
3. The OS process boundary: the parent kills it on timeout and gives it no secrets in its environment.

This file must stay self-contained: it is executed in isolated mode without the project on sys.path.
"""
import ast
import builtins
import importlib
import linecache
import re
import sys
import traceback
import types

FILENAME = "<code>"

ALLOWED_MODULES = frozenset({
    "array", "base64", "binascii", "bisect", "calendar", "cmath", "collections", "copy", "datetime",
    "decimal", "enum", "fractions", "functools", "hashlib", "heapq", "itertools", "json", "math",
    "numbers", "operator", "pprint", "random", "re", "statistics", "string", "textwrap", "time",
    "unicodedata", "uuid", "zoneinfo", "collections.abc",
})

BLOCKED_NAMES = frozenset({
    "eval", "exec", "compile", "open", "input", "breakpoint", "help", "exit", "quit", "globals",
    "locals", "vars", "memoryview", "__import__", "__builtins__", "__loader__", "__spec__",
})

# Non-underscore attributes that still reach frames, globals or code objects.
BLOCKED_ATTRS = frozenset({
    "gi_frame", "gi_code", "gi_yieldfrom", "cr_frame", "cr_code", "cr_await", "ag_frame", "ag_code",
    "ag_await", "f_globals", "f_locals", "f_builtins", "f_back", "f_code", "tb_frame", "tb_next",
})

_FORMAT_ATTR_RE = re.compile(r"\{[^{}]*\.(?:_|" + "|".join(sorted(BLOCKED_ATTRS)) + r")")

SAFE_BUILTINS = [
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable", "chr", "classmethod",
    "complex", "dict", "dir", "divmod", "enumerate", "filter", "float", "format", "frozenset", "hash",
    "hex", "id", "int", "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min", "next",
    "object", "oct", "ord", "pow", "print", "property", "range", "repr", "reversed", "round", "set",
    "slice", "sorted", "staticmethod", "str", "sum", "super", "tuple", "type", "zip",
    "NotImplemented", "Ellipsis", "__build_class__",
]


def _private_attr_allowed(node: ast.Attribute) -> bool:
    """`self._x` / `cls._x` are allowed so classes work normally; dunders never are."""
    return (
        not node.attr.startswith("__")
        and isinstance(node.value, ast.Name)
        and node.value.id in ("self", "cls")
    )


def validate(code: str) -> list:
    """Return a list of human-readable problems; empty means the code may run. Raises SyntaxError."""
    tree = ast.parse(code, FILENAME, "exec")
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_MODULES:
                    problems.append(f"line {node.lineno}: importing '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module not in ALLOWED_MODULES:
                problems.append(f"line {node.lineno}: importing from '{node.module or '.'}' is not allowed")
            elif any(alias.name.startswith("_") for alias in node.names):
                problems.append(f"line {node.lineno}: importing private names is not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_ATTRS or (node.attr.startswith("_") and not _private_attr_allowed(node)):
                problems.append(f"line {node.lineno}: access to attribute '{node.attr}' is not allowed")
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES or (node.id.startswith("__") and node.id != "__name__"):
                problems.append(f"line {node.lineno}: '{node.id}' is not available in the sandbox")
        elif isinstance(node, ast.MatchClass):
            if any(attr.startswith("_") for attr in node.kwd_attrs):
                problems.append(f"line {node.lineno}: matching on private attributes is not allowed")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _FORMAT_ATTR_RE.search(node.value):
                problems.append(f"line {node.lineno}: format strings may not access private attributes")
    return problems


def _check_attr_name(name) -> None:
    if not isinstance(name, str):
        raise TypeError("attribute name must be a string")
    for part in name.split("."):
        if part.startswith("_") or part in BLOCKED_ATTRS:
            raise AttributeError(f"access to attribute '{name}' is not allowed")


def _safe_attrgetter(*names):
    import operator

    for name in names:
        _check_attr_name(name)
    return operator.attrgetter(*names)


def _safe_methodcaller(name, *args, **kwargs):
    import operator

    _check_attr_name(name)
    return operator.methodcaller(name, *args, **kwargs)


# Library functions that look attributes up from runtime strings, which the AST check can't see.
_MODULE_OVERRIDES = {
    ("operator", "attrgetter"): _safe_attrgetter,
    ("operator", "methodcaller"): _safe_methodcaller,
}
_MODULE_BLOCKED = {("string", "Formatter")}


def _module_proxy(module):
    """Wrap a module so only its public, non-module attributes (or allowed submodules) are reachable."""

    class ModuleProxy:
        __slots__ = ()

        def __getattr__(self, name):
            if name == "__all__":
                return [
                    n for n in dir(module)
                    if not n.startswith("_") and not isinstance(getattr(module, n, None), types.ModuleType)
                ]
            if name.startswith("_") or name in BLOCKED_ATTRS or (module.__name__, name) in _MODULE_BLOCKED:
                raise AttributeError(f"module '{module.__name__}' has no accessible attribute '{name}'")
            if (module.__name__, name) in _MODULE_OVERRIDES:
                return _MODULE_OVERRIDES[(module.__name__, name)]
            value = getattr(module, name)
            if isinstance(value, types.ModuleType):
                if value.__name__ in ALLOWED_MODULES:
                    return _module_proxy(value)
                raise AttributeError(f"access to module '{value.__name__}' is not allowed")
            return value

        def __repr__(self):
            return f"<module '{module.__name__}'>"

    return ModuleProxy()


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name not in ALLOWED_MODULES:
        raise ImportError(f"importing '{name}' is not allowed in the sandbox")
    module = importlib.import_module(name)
    if fromlist:
        return _module_proxy(module)
    return _module_proxy(importlib.import_module(name.split(".")[0]))


def _safe_getattr(obj, name, *default):
    if not isinstance(name, str) or name.startswith("_") or name in BLOCKED_ATTRS:
        raise AttributeError(f"access to attribute '{name}' is not allowed")
    return getattr(obj, name, *default)


def _safe_hasattr(obj, name):
    try:
        _safe_getattr(obj, name)
        return True
    except AttributeError:
        return False


def _build_builtins() -> dict:
    safe = {name: getattr(builtins, name) for name in SAFE_BUILTINS}
    for name, value in vars(builtins).items():
        if isinstance(value, type) and issubclass(value, BaseException):
            safe[name] = value
    safe.update(__import__=_safe_import, getattr=_safe_getattr, hasattr=_safe_hasattr, __name__="builtins")
    return safe


def _print_error(exc: BaseException) -> None:
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == FILENAME]
    lines = []
    if frames:
        lines.append("Traceback (most recent call last):\n")
        lines.extend(traceback.format_list(frames))
    lines.extend(traceback.format_exception_only(type(exc), exc))
    sys.stderr.write("".join(lines))


def run(code: str) -> int:
    try:
        problems = validate(code)
    except SyntaxError as e:
        sys.stderr.write("".join(traceback.format_exception_only(type(e), e)))
        return 1
    if problems:
        sys.stderr.write("Blocked by sandbox:\n" + "\n".join(f"  - {p}" for p in problems) + "\n")
        return 2

    linecache.cache[FILENAME] = (len(code), None, code.splitlines(True), FILENAME)
    tree = ast.parse(code, FILENAME, "exec")
    # Like a REPL, echo the value of a trailing bare expression (e.g. "2 ** 100").
    echo = None
    last = tree.body[-1] if tree.body else None
    if isinstance(last, ast.Expr) and not (
        isinstance(last.value, ast.Call) and isinstance(last.value.func, ast.Name) and last.value.func.id == "print"
    ):
        tree.body.pop()
        echo = compile(ast.Expression(last.value), FILENAME, "eval")

    # User code runs as a fresh __main__ module so anything that resolves a class's module through
    # sys.modules (e.g. annotation evaluation) sees the restricted namespace, not this runner's.
    main = types.ModuleType("__main__")
    namespace = main.__dict__
    namespace["__builtins__"] = _build_builtins()
    sys.modules["__main__"] = main
    try:
        exec(compile(tree, FILENAME, "exec"), namespace)
        if echo is not None:
            value = eval(echo, namespace)
            if value is not None:
                print(repr(value))
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    except BaseException as e:
        sys.stdout.flush()
        _print_error(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    source = sys.stdin.buffer.read().decode("utf-8")
    sys.stdin = None
    exit_code = run(source)
    sys.stdout.flush()
    sys.exit(exit_code)
