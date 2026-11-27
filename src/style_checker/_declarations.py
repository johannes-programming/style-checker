#!/usr/bin/env python3
"""
Check module-level and function-local variable declaration style rules.

Rule implemented
----------------
At module level and inside every ``def`` or ``async def``:

* variables bound by assignment-like syntax in their scope must first be
    declared with a bare type annotation, e.g. ``count: int``;
* declarations must form one block at the beginning of the scope
    (an optional docstring may precede them; nested classes may be interleaved
    within the block in function scopes);
* declarations must not assign a value;
* declaration names must be in alphabetical order;
* ``Final`` annotations are initialized in place, outside the declaration
    block and at the indentation level of their namespace (also in classes);
* every function parameter must have a type annotation;
* function parameters must not be reassigned;
* undecorated methods and functions directly decorated by ``@classmethod``
    must have a positional-only first parameter.

Imports may precede the declaration block in either scope, and module-level
``__all__`` is subject to its own separate rules.

Function parameters, ``global`` names, and ``nonlocal`` names are exempt from
local-variable declarations.
Nested functions/classes are checked independently and their bodies are not
treated as part of the enclosing function.

Each distinct file, physical line, and rule produces one report line.
"""

from __future__ import annotations

__all__: list[str] = [
    "scan",
]

import ast
import io
import symtable
import tokenize
from bisect import bisect_left
from collections import Counter
from collections import abc as collections_abc
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class FunctionViolation:
    file: str
    line: int
    rule: str
    desc: str


class _Rule(Enum):
    LINE_NL = "nonempty files must end with a linebreak"
    LINE_BL = "whitespace-only lines at end of file"
    LINE_TW = "trailing whitespace on physical lines"
    LINE_IND = "indentation must be four spaces per level"
    LINE_CONT = "physical lines indented two or more levels deeper"
    LINE_DEEP = "simple statements indented more than four levels"
    STMT_BEG = "simple statements not at beginning of physical line"
    ALL_IMP = "'__all__' must precede imports"
    ALL_MIS = "missing '__all__'"
    ALL_DUP = "multiple '__all__' assignments"
    ALL_TYPE = "'__all__' must be annotated as 'list[str]'"
    ALL_LIST = "'__all__' must be assigned a list literal"
    ALL_STR = "'__all__' items must be string literals"
    ALL_ORD = "'__all__' items not in alphabetical order"
    IMPT_WILD = "wildcard imports are forbidden"
    IMPT_TYPE = "'typing' imports available in 'collections.abc'"
    DEAD_NAME = "dead module names"
    FUNC_ARG = "unannotated arguments"
    FUNC_ASGN = "reassigned parameters"
    FUNC_KWOR = "keyword-only arguments not in alphabetical order"
    FUNC_POS = "first argument must be positional-only"
    PLAC_BEG = "declarations not at beginning"
    FIN_PLAC = "Final annotations not at namespace indentation level"
    FIN_VAL = "Final annotation has no assignment"
    REQD_ORD = "declarations not in alphabetical order"
    EXEM_IMP = "declarations for 'def'/'class'/'import' names"
    EXEM_EX = "declarations for 'except' names"
    REQD_DUP = "duplicate declarations"
    REQD_MIS = "missing declarations"
    EXEM_UN = "unnecessary declarations"
    REQD_VAL = "declaration assigns a value"

    @property
    def mark(self: Self, /) -> str:
        return self.name.replace("_", "-")


def _is_ignored(rule: str, ignore: frozenset[str]) -> bool:
    return "" in ignore or rule in ignore or rule.partition("-")[0] in ignore


class _LineIssues:
    """Collect one set of details per physical line and rule."""

    def __init__(self: Self, /, ignore: frozenset[str]) -> None:
        self.by_line: dict[int, dict[_Rule, set[str]]] = {}
        self.ignore: frozenset[str] = ignore

    def add(
        self: Self,
        /,
        line: int,
        rule: _Rule,
        detail: str = "",
    ) -> None:
        if _is_ignored(rule.mark, self.ignore):
            return
        self.by_line.setdefault(line, {}).setdefault(rule, set()).add(detail)

    def names(
        self: Self, /, rule: _Rule, findings: Iterator[tuple[int, str]]
    ) -> None:
        line: int
        name: str
        for line, name in findings:
            self.add(line, rule, repr(name))

    def violations(self: Self, /, path: str) -> Iterator[FunctionViolation]:
        description: str
        detail: str
        details: set[str]
        line: int
        rule: _Rule
        rules: dict[_Rule, set[str]]
        for line, rules in sorted(self.by_line.items()):
            for rule, details in sorted(
                rules.items(), key=lambda item: item[0].mark
            ):
                description = rule.value
                detail = ", ".join(sorted(details - {""}))
                description = ": ".join(filter(None, (description, detail)))
                yield FunctionViolation(path, line, rule.mark, description)


class _SourceLocations:
    """Locate evidence in physical source order rather than AST walk order."""

    def __init__(self: Self, /, source: str) -> None:
        ignored: set[int]
        self.lines = source.encode("utf-8").split(b"\n")
        self.last_line = max(1, len(self.lines) - source.endswith("\n"))
        ignored = {
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.COMMENT,
            tokenize.ENDMARKER,
        }
        self.tokens = [
            token
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type not in ignored
        ]
        self.positions = [token.start for token in self.tokens]
        self.prefix_end: int | None = None
        self.next_token: tokenize.TokenInfo | None = None

    def after(
        self: Self,
        /,
        node: ast.expr | ast.arg | ast.stmt,
    ) -> Iterator[tokenize.TokenInfo]:
        column: int
        line: int
        start: int
        line = node.end_lineno or node.lineno
        column = len(
            self.lines[line - 1][: node.end_col_offset].decode("utf-8")
        )
        start = bisect_left(self.positions, (line, column))
        return (self.tokens[i] for i in range(start, len(self.tokens)))

    def following(
        self: Self,
        /,
        node: ast.expr | ast.arg | ast.stmt,
        symbols: set[str],
    ) -> int:
        token: tokenize.TokenInfo
        for token in self.after(node):
            if token.string in symbols:
                return token.start[0]
        return node.end_lineno or node.lineno

    def scope_end(self: Self, /, node: ast.Module | ast.stmt) -> int:
        token: tokenize.TokenInfo | None
        if isinstance(node, ast.Module):
            return self.last_line
        # A trailing semicolon is part of the last body line, not a dedent.
        token = next(
            (token for token in self.after(node) if token.string != ";"), None
        )
        if self.prefix_end is not None and (
            token is None or token.start[0] > self.prefix_end
        ):
            # A real dedent can precede the error even when the next
            # statement is malformed. An artificial EOF cannot close a scope.
            token = self.next_token
            if (
                token is not None
                and node.end_lineno is not None
                and node.end_lineno <= self.prefix_end
                and token.start[1] <= node.col_offset
            ):
                return token.start[0]
            return self.last_line
        return token.start[0] if token is not None else self.last_line

    def exception_name(self: Self, /, node: ast.ExceptHandler) -> int:
        token: tokenize.TokenInfo
        tokens: Iterator[tokenize.TokenInfo]
        assert node.type is not None
        tokens = self.after(node.type)
        for token in tokens:
            if token.string == "as":
                return next(tokens).start[0]
        return node.lineno

    def mapping_rest(self: Self, /, node: ast.MatchMapping) -> int:
        # The rest capture is the final name before the closing brace.
        column: int
        i: int
        line: int
        line = node.end_lineno or node.lineno
        column = len(
            self.lines[line - 1][: node.end_col_offset].decode("utf-8")
        )
        i = bisect_left(self.positions, (line, column)) - 1
        while i >= 0:
            if self.tokens[i].type == tokenize.NAME:
                return self.tokens[i].start[0]
            i -= 1
        return node.lineno

    def definition_name(
        self: Self,
        /,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> int:
        i: int
        start: int
        start = bisect_left(self.positions, (node.lineno, 0))
        for i in range(start, len(self.tokens) - 1):
            if self.tokens[i].string in {"def", "class"}:
                return self.tokens[i + 1].start[0]
        return node.lineno

    def parameter_end(self: Self, /, arg: ast.arg) -> int:
        return self.following(arg, {",", ")", "="})

    def positional_only_end(
        self: Self,
        /,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> int:
        # A slash could still follow an ordinary positional parameter, even
        # on a later line. Its absence is certain at a star or closing paren.
        args: ast.arguments
        boundary: tuple[int, int]
        column: int
        depth: int
        i: int
        last: ast.arg | ast.expr | None
        line: int
        opened: bool
        start: int
        token: tokenize.TokenInfo
        opened = False
        depth = 0
        # Ignore multiplication and unpacking within positional defaults or
        # annotations, even when the operator is at signature depth one.
        args = node.args
        last = None
        if args.defaults:
            last = args.defaults[-1]
        elif args.args:
            last = args.args[-1]
        boundary = (0, 0)
        if last is not None:
            line = last.end_lineno or last.lineno
            column = len(
                self.lines[line - 1][: last.end_col_offset].decode("utf-8")
            )
            boundary = (line, column)
        start = bisect_left(self.positions, (node.lineno, 0))
        for i in range(start, len(self.tokens)):
            token = self.tokens[i]
            if not opened and token.string == "(":
                opened = True
                depth = 1
                continue
            if not opened:
                continue
            if (
                depth == 1
                and token.start >= boundary
                and token.string in {"*", "**", ")"}
            ):
                return token.start[0]
            if token.string in {"(", "[", "{"}:
                depth += 1
            elif token.string in {")", "]", "}"}:
                depth -= 1
        return node.lineno


def _first_line(lines: dict[str, int], name: str, line: int) -> None:
    lines[name] = min(lines.get(name, line), line)


def _is_docstring_statement(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_bare_name_declaration(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is None
        and node.simple == 1
    )


def _is_module_all_statement(node: ast.stmt) -> bool:
    """Exclude ``__all__`` from the ordinary module-variable rules."""
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return (
            isinstance(node.target, ast.Name) and node.target.id == "__all__"
        )
    if isinstance(node, ast.Assign):
        return all(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    return False


def _check_module_all(
    body: list[ast.stmt],
    locations: _SourceLocations,
    issues: _LineIssues,
) -> None:
    """Validate the special module-level ``__all__`` declaration."""
    _: int
    greatest: str | None
    index: int
    indices: Iterator[int]
    item: ast.expr
    line: int
    matches: list[tuple[int, ast.stmt]]
    previous: ast.stmt
    repeated: ast.stmt
    start: int
    stmt: ast.stmt
    value: ast.expr | None
    matches = [
        (index, stmt)
        for index, stmt in enumerate(body)
        if _is_module_all_statement(stmt)
    ]
    index = matches[0][0] if matches else len(body)
    for previous in body[:index]:
        if not isinstance(previous, (ast.Import, ast.ImportFrom)):
            continue
        if (
            isinstance(previous, ast.ImportFrom)
            and previous.level == 0
            and previous.module == "__future__"
        ):
            continue
        line = previous.lineno
        if isinstance(previous, ast.ImportFrom):
            start = bisect_left(locations.positions, (line, 0))
            indices = (
                locations.tokens[i + 1].start[0]
                for i in range(start, len(locations.tokens) - 1)
                if locations.tokens[i].string == "from"
            )
            line = next(indices, line)
        issues.add(line, _Rule.ALL_IMP)
        break
    if not matches:
        issues.add(locations.last_line, _Rule.ALL_MIS)
        return
    _, stmt = matches[0]
    for _, repeated in matches[1:]:
        issues.add(repeated.lineno, _Rule.ALL_DUP)

    if not (
        isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.annotation, ast.Subscript)
        and isinstance(stmt.annotation.value, ast.Name)
        and stmt.annotation.value.id == "list"
        and isinstance(stmt.annotation.slice, ast.Name)
        and stmt.annotation.slice.id == "str"
    ):
        if isinstance(stmt, ast.AnnAssign):
            line = stmt.annotation.end_lineno or stmt.annotation.lineno
        elif isinstance(stmt, ast.Assign):
            line = locations.following(stmt.targets[0], {"="})
        else:
            line = stmt.lineno
        issues.add(line, _Rule.ALL_TYPE)
    value = (
        stmt.value if isinstance(stmt, (ast.AnnAssign, ast.Assign)) else None
    )
    if not isinstance(value, ast.List):
        line = (
            (value.end_lineno or value.lineno)
            if value is not None
            else (stmt.end_lineno or stmt.lineno)
        )
        issues.add(line, _Rule.ALL_LIST)
        return
    greatest = None
    for item in value.elts:
        line = item.end_lineno or item.lineno
        if not isinstance(item, ast.Constant) or not isinstance(
            item.value, str
        ):
            issues.add(line, _Rule.ALL_STR)
        elif greatest is not None and item.value < greatest:
            issues.add(line, _Rule.ALL_ORD)
        else:
            greatest = item.value


class _FunctionAnnotations(ast.NodeVisitor):
    """Collect scope annotations without descending into nested scopes."""

    def __init__(self: Self, /) -> None:
        self.annotations: list[ast.AnnAssign] = []
        self.final_imports: set[str] = set()

    def visit_Import(self: Self, /, node: ast.Import) -> None:
        alias: ast.alias
        for alias in node.names:
            if alias.name in {"typing", "typing_extensions"}:
                self.final_imports.add((alias.asname or alias.name) + ".Final")

    def visit_ImportFrom(self: Self, /, node: ast.ImportFrom) -> None:
        alias: ast.alias
        if node.level != 0 or node.module not in {
            "typing",
            "typing_extensions",
        }:
            return
        for alias in node.names:
            if alias.name == "Final":
                self.final_imports.add(alias.asname or alias.name)

    def visit_AnnAssign(self: Self, /, node: ast.AnnAssign) -> None:
        self.annotations.append(node)

    def visit_FunctionDef(self: Self, /, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(
        self: Self, /, node: ast.AsyncFunctionDef
    ) -> None:
        return

    def visit_ClassDef(self: Self, /, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self: Self, /, node: ast.Lambda) -> None:
        return


def _collect_annotations(body: list[ast.stmt]) -> _FunctionAnnotations:
    collector: _FunctionAnnotations
    statement: ast.stmt

    collector = _FunctionAnnotations()
    for statement in body:
        collector.visit(statement)
    return collector


def _function_annotations(body: list[ast.stmt]) -> list[ast.AnnAssign]:
    return _collect_annotations(body).annotations


def _is_final_annotation(annotation: ast.expr, imports: set[str]) -> bool:
    target: ast.expr
    target = (
        annotation.value
        if isinstance(annotation, ast.Subscript)
        else annotation
    )
    if isinstance(target, ast.Name):
        return target.id in imports
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and f"{target.value.id}.{target.attr}" in imports
    )


class _FunctionBodyFacts(ast.NodeVisitor):
    """Collect scope binding/read facts without descending into nested scopes."""

    def __init__(
        self: Self,
        /,
        locations: _SourceLocations | None = None,
    ) -> None:
        self.locations = locations
        self.binding_floor = 0
        self.binding_lines: dict[str, int] = {}
        self.non_variable_lines: dict[str, int] = {}
        self.exception_lines: dict[str, int] = {}
        self.typevar_lines: dict[str, int] = {}
        self.bound: set[str] = set()
        self.read: set[str] = set()
        self.first_kind: dict[str, str] = {}
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()
        self.non_variable_bindings: set[str] = set()
        self.exception_bindings: set[str] = set()
        self.typevar_bindings: set[str] = set()
        self.typevar_factories: set[str] = set()
        self.typevar_modules: set[str] = {"typing", "typing_extensions"}
        self.wildcard_imports: set[int] = set()
        self.forbidden_typing_imports: set[tuple[int, str]] = set()

    def import_issues(self: Self, /, issues: _LineIssues) -> None:
        line: int
        for line in sorted(self.wildcard_imports):
            issues.add(line, _Rule.IMPT_WILD)
        issues.names(
            _Rule.IMPT_TYPE,
            iter(sorted(self.forbidden_typing_imports)),
        )

    def _non_variable(self: Self, /, name: str, line: int) -> None:
        self.non_variable_bindings.add(name)
        _first_line(self.non_variable_lines, name, line)

    def _assignment_target(
        self: Self,
        /,
        target: ast.expr,
        line: int,
    ) -> None:
        previous: int
        previous = self.binding_floor
        self.binding_floor = line
        self.visit(target)
        self.binding_floor = previous

    def _is_typevar_call(self: Self, /, value: ast.expr) -> bool:
        func: ast.expr

        if not isinstance(value, ast.Call):
            return False
        func = value.func
        if isinstance(func, ast.Name):
            return func.id in self.typevar_factories
        return (
            isinstance(func, ast.Attribute)
            and func.attr
            in {"TypeVar", "ParamSpec", "TypeVarTuple", "TypeAliasType"}
            and isinstance(func.value, ast.Name)
            and func.value.id in self.typevar_modules
        )

    def _record(self: Self, /, name: str, kind: str, line: int) -> None:
        if name not in self.first_kind:
            self.first_kind[name] = kind
        if kind == "bind":
            self.bound.add(name)
            _first_line(
                self.binding_lines, name, max(line, self.binding_floor)
            )
        elif kind == "read":
            self.read.add(name)

    def visit_Name(self: Self, /, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record(node.id, "read", node.lineno)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self._record(node.id, "bind", node.lineno)

    def visit_Import(self: Self, /, node: ast.Import) -> None:
        alias: ast.alias

        for alias in node.names:
            self._non_variable(
                alias.asname or alias.name.split(".", 1)[0],
                alias.end_lineno or alias.lineno,
            )
            if alias.name in {"typing", "typing_extensions"}:
                self.typevar_modules.add(alias.asname or alias.name)

    def visit_ImportFrom(self: Self, /, node: ast.ImportFrom) -> None:
        alias: ast.alias

        if node.level == 0 and node.module == "__future__":
            return  # Compiler directives do not bind runtime names.
        for alias in node.names:
            if alias.name == "*":
                self.wildcard_imports.add(alias.lineno)
            elif (
                node.level == 0
                and node.module == "typing"
                and alias.name in collections_abc.__all__
            ):
                self._non_variable(
                    alias.asname or alias.name,
                    alias.end_lineno or alias.lineno,
                )
                self.forbidden_typing_imports.add((alias.lineno, alias.name))
            else:
                self._non_variable(
                    alias.asname or alias.name,
                    alias.end_lineno or alias.lineno,
                )
            if node.module in {
                "typing",
                "typing_extensions",
            } and alias.name in {
                "TypeVar",
                "ParamSpec",
                "TypeVarTuple",
                "TypeAliasType",
            }:
                self.typevar_factories.add(alias.asname or alias.name)

    def visit_Assign(self: Self, /, node: ast.Assign) -> None:
        # Python evaluates the RHS before binding assignment targets.
        line: int
        target: ast.expr

        self.visit(node.value)
        if self._is_typevar_call(node.value):
            self.typevar_bindings.update(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            )
        for target in node.targets:
            line = (
                self.locations.following(target, {"="})
                if self.locations
                else target.lineno
            )
            if isinstance(target, ast.Name) and self._is_typevar_call(
                node.value
            ):
                _first_line(self.typevar_lines, target.id, node.value.lineno)
            self._assignment_target(target, line)

    def visit_AnnAssign(self: Self, /, node: ast.AnnAssign) -> None:
        # Evaluate annotation/value before treating the target as bound.
        line: int
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
            line = (
                self.locations.following(node.annotation, {"="})
                if self.locations
                else node.lineno
            )
            self._assignment_target(node.target, line)
        # A bare annotation is a declaration, not a runtime assignment.

    def visit_AugAssign(self: Self, /, node: ast.AugAssign) -> None:
        # ``x += y`` reads x before it writes x.
        line: int
        operators: set[str]
        if isinstance(node.target, ast.Name):
            self._record(node.target.id, "read", node.target.lineno)
            self.visit(node.value)
            line = node.target.lineno
            if self.locations:
                operators = {
                    "+=",
                    "-=",
                    "*=",
                    "@=",
                    "/=",
                    "//=",
                    "%=",
                    "**=",
                    "<<=",
                    ">>=",
                    "&=",
                    "^=",
                    "|=",
                }
                line = self.locations.following(node.target, operators)
            self._record(node.target.id, "bind", line)
        else:
            self.visit(node.target)
            self.visit(node.value)

    def visit_NamedExpr(self: Self, /, node: ast.NamedExpr) -> None:
        line: int
        self.visit(node.value)
        line = (
            self.locations.following(node.target, {":="})
            if self.locations
            else node.target.lineno
        )
        self._assignment_target(node.target, line)

    def visit_For(self: Self, /, node: ast.For | ast.AsyncFor) -> None:
        statement: ast.stmt

        self.visit(node.iter)
        self.visit(node.target)
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)

    def visit_AsyncFor(self: Self, /, node: ast.AsyncFor) -> None:
        self.visit_For(node)

    def visit_With(self: Self, /, node: ast.With | ast.AsyncWith) -> None:
        item: ast.withitem
        statement: ast.stmt

        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self.visit(item.optional_vars)
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncWith(self: Self, /, node: ast.AsyncWith) -> None:
        self.visit_With(node)

    def visit_MatchAs(self: Self, /, node: ast.MatchAs) -> None:
        # Capture names are strings in the AST, not ast.Name targets.
        self.generic_visit(node)
        if node.name is not None:
            self._record(node.name, "bind", node.end_lineno or node.lineno)

    def visit_MatchStar(self: Self, /, node: ast.MatchStar) -> None:
        if node.name is not None:
            self._record(node.name, "bind", node.end_lineno or node.lineno)

    def visit_MatchMapping(self: Self, /, node: ast.MatchMapping) -> None:
        line: int
        self.generic_visit(node)
        if node.rest is not None:
            line = (
                self.locations.mapping_rest(node)
                if self.locations
                else node.lineno
            )
            self._record(node.rest, "bind", line)

    def visit_ExceptHandler(self: Self, /, node: ast.ExceptHandler) -> None:
        line: int
        statement: ast.stmt

        if node.type is not None:
            self.visit(node.type)
        if node.name is not None:
            # ``except ... as name`` is a temporary exception binding, not a
            # function-local variable governed by the declaration rule.
            self.exception_bindings.add(node.name)
            line = (
                self.locations.exception_name(node)
                if self.locations
                else node.lineno
            )
            _first_line(self.exception_lines, node.name, line)
        for statement in node.body:
            self.visit(statement)

    def visit_Global(self: Self, /, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self: Self, /, node: ast.Nonlocal) -> None:
        self.nonlocals.update(node.names)

    def visit_FunctionDef(self: Self, /, node: ast.FunctionDef) -> None:
        # The nested function's name is not treated as a "variable" for this
        # rule, and its body belongs to a different function scope.
        self._non_variable(
            node.name,
            self.locations.definition_name(node)
            if self.locations
            else node.lineno,
        )

    def visit_AsyncFunctionDef(
        self: Self, /, node: ast.AsyncFunctionDef
    ) -> None:
        self._non_variable(
            node.name,
            self.locations.definition_name(node)
            if self.locations
            else node.lineno,
        )

    def visit_ClassDef(self: Self, /, node: ast.ClassDef) -> None:
        self._non_variable(
            node.name,
            self.locations.definition_name(node)
            if self.locations
            else node.lineno,
        )

    def visit_Lambda(self: Self, /, node: ast.Lambda) -> None:
        return

    def visit_comprehension(self: Self, /, node: ast.comprehension) -> None:
        # Comprehension iteration variables live in the comprehension's own
        # implicit scope in Python 3.
        condition: ast.expr

        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def visit_ListComp(self: Self, /, node: ast.ListComp) -> None:
        generator: ast.comprehension

        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator)

    def visit_SetComp(self: Self, /, node: ast.SetComp) -> None:
        generator: ast.comprehension

        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator)

    def visit_DictComp(self: Self, /, node: ast.DictComp) -> None:
        generator: ast.comprehension

        self.visit(node.key)
        self.visit(node.value)
        for generator in node.generators:
            self.visit(generator)

    def visit_GeneratorExp(self: Self, /, node: ast.GeneratorExp) -> None:
        generator: ast.comprehension

        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator)


def _parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> set[str]:
    args: ast.arguments
    result: set[str]

    args = node.args
    result = {arg.arg for arg in args.posonlyargs}
    result.update(arg.arg for arg in args.args)
    result.update(arg.arg for arg in args.kwonlyargs)
    if args.vararg is not None:
        result.add(args.vararg.arg)
    if args.kwarg is not None:
        result.add(args.kwarg.arg)
    return result


class _ParameterAssignments(_FunctionBodyFacts):
    """Collect every parameter rebinding, including writes through nonlocal."""

    def __init__(
        self: Self,
        /,
        locations: _SourceLocations,
        parameters: set[str] | None = None,
    ) -> None:
        super().__init__(locations)
        self.parameters = parameters
        self.assignments: set[tuple[int, str]] = set()
        self.annotated_names: set[str] = set()
        self.children: list[_ParameterAssignments] = []

    def _record(self: Self, /, name: str, kind: str, line: int) -> None:
        super()._record(name, kind, line)
        if kind == "bind":
            self.assignments.add((max(line, self.binding_floor), name))

    def _non_variable(self: Self, /, name: str, line: int) -> None:
        super()._non_variable(name, line)
        self.assignments.add((line, name))

    def visit_Name(self: Self, /, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Del):
            # Deletion establishes a local name, but is not reassignment.
            super()._record(node.id, "bind", node.lineno)
        else:
            super().visit_Name(node)

    def visit_AnnAssign(self: Self, /, node: ast.AnnAssign) -> None:
        if node.simple and isinstance(node.target, ast.Name):
            self.annotated_names.add(node.target.id)
        super().visit_AnnAssign(node)
        if node.value is None and not isinstance(node.target, ast.Name):
            self.visit(node.target)

    def visit_ExceptHandler(self: Self, /, node: ast.ExceptHandler) -> None:
        super().visit_ExceptHandler(node)
        if node.name is not None:
            assert self.locations is not None
            self.assignments.add(
                (self.locations.exception_name(node), node.name)
            )

    def _child(
        self: Self, /, parameters: set[str] | None, body: list[ast.AST]
    ) -> None:
        child: _ParameterAssignments
        statement: ast.AST
        assert self.locations is not None
        child = _ParameterAssignments(self.locations, parameters)
        self.children.append(child)
        for statement in body:
            child.visit(statement)

    def visit_FunctionDef(self: Self, /, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(
        self: Self, /, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_function(node)

    def _visit_function(
        self: Self, /, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        decorator: ast.expr
        assert self.locations is not None
        self._non_variable(node.name, self.locations.definition_name(node))
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit(node.args)
        if node.returns is not None:
            self.visit(node.returns)
        self._child(_parameter_names(node), list(node.body))

    def visit_ClassDef(self: Self, /, node: ast.ClassDef) -> None:
        header: ast.AST
        super().visit_ClassDef(node)
        for header in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(header)
        self._child(None, list(node.body))

    def visit_Lambda(self: Self, /, node: ast.Lambda) -> None:
        self.visit(node.args)
        self._child(_parameter_names(node), [node.body])

    def report(
        self: Self,
        /,
        issues: _LineIssues,
        enclosing: list[_ParameterAssignments],
    ) -> None:
        child: _ParameterAssignments
        child_enclosing: list[_ParameterAssignments]
        line: int
        name: str
        for line, name in self.assignments:
            if self.parameters is not None and name in self.parameters:
                issues.add(line, _Rule.FUNC_ASGN, repr(name))
            elif name in self.nonlocals and self._outer_parameter(
                name, enclosing
            ):
                issues.add(line, _Rule.FUNC_ASGN, repr(name))
        child_enclosing = enclosing
        if self.parameters is not None:
            child_enclosing = [*enclosing, self]
        for child in self.children:
            child.report(issues, child_enclosing)

    def _outer_parameter(
        self: Self, /, name: str, enclosing: list[_ParameterAssignments]
    ) -> bool:
        outer: _ParameterAssignments
        for outer in reversed(enclosing):
            if name in outer.globals or name in outer.nonlocals:
                continue
            if name in (
                (outer.parameters or set())
                | outer.bound
                | outer.non_variable_bindings
                | outer.exception_bindings
                | outer.annotated_names
            ):
                return name in (outer.parameters or set())
        return False


def _unannotated_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg]:
    args: ast.arguments
    parameters: list[ast.arg]

    args = node.args
    parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        parameters.append(args.vararg)
    if args.kwarg is not None:
        parameters.append(args.kwarg)
    return [arg for arg in parameters if arg.annotation is None]


def _collect_body_facts(
    body: list[ast.stmt],
    declaration_nodes: set[int],
    locations: _SourceLocations | None = None,
) -> _FunctionBodyFacts:
    facts: _FunctionBodyFacts
    statement: ast.stmt

    facts = _FunctionBodyFacts(locations)

    for statement in body:
        # Leading declarations are declarations only, not first "uses".
        if id(statement) in declaration_nodes:
            # Still visit the annotation expression, since it may reference
            # names, but never treat the declared target as a binding/use.
            assert isinstance(statement, ast.AnnAssign)
            facts.visit(statement.annotation)
            continue
        facts.visit(statement)

    return facts


def _dead_module_names(
    module: ast.Module, source: str, filename: str
) -> list[str]:
    """Find module bindings neither exported through __all__ nor read here."""
    annotation: ast.expr | None
    candidates: set[str]
    exported: set[str]
    facts: _FunctionBodyFacts
    node: ast.AST
    refs: set[str]
    scope: symtable.SymbolTable
    scopes: list[symtable.SymbolTable]
    statement: ast.stmt
    symbol: symtable.Symbol

    facts = _collect_body_facts(module.body, set())
    candidates = facts.bound | facts.non_variable_bindings
    candidates -= {
        "__all__",
        "__annotations__",
        "__builtins__",
        "__cached__",
        "__doc__",
        "__file__",
        "__loader__",
        "__name__",
        "__package__",
        "__path__",
        "__spec__",
    }
    exported = set()
    for statement in module.body:
        if (
            _is_module_all_statement(statement)
            and isinstance(statement, (ast.Assign, ast.AnnAssign))
            and isinstance(statement.value, ast.List)
        ):
            exported.update(
                item.value
                for item in statement.value.elts
                if isinstance(item, ast.Constant)
                and isinstance(item.value, str)
            )

    refs = set()
    scopes = [symtable.symtable(source, filename, "exec")]
    while scopes:
        scope = scopes.pop()
        for symbol in scope.get_symbols():
            if symbol.is_referenced() and (
                scope.get_type() == "module" or symbol.is_global()
            ):
                refs.add(symbol.get_name())
        scopes.extend(scope.get_children())

    # Postponed annotations are not counted as reads by symtable, but they
    # still refer to imported or declared types in the source.
    if any(
        isinstance(stmt, ast.ImportFrom)
        and stmt.level == 0
        and stmt.module == "__future__"
        and any(alias.name == "annotations" for alias in stmt.names)
        for stmt in module.body
    ):
        for node in ast.walk(module):
            annotation = None
            if isinstance(node, ast.AnnAssign):
                annotation = node.annotation
            elif isinstance(node, ast.arg):
                annotation = node.annotation
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                annotation = node.returns
            if annotation is not None:
                refs.update(
                    name.id
                    for name in ast.walk(annotation)
                    if isinstance(name, ast.Name)
                    and isinstance(name.ctx, ast.Load)
                )

    return sorted(candidates - exported - refs)


def _statement_placement_visit(
    node: ast.AST,
    source_lines: list[bytes],
    line_numbers: set[int],
) -> None:
    child: ast.AST
    if isinstance(node, ast.stmt):
        if source_lines[node.lineno - 1][: node.col_offset].strip():
            line_numbers.add(node.lineno)
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            return
    for child in ast.iter_child_nodes(node):
        _statement_placement_visit(child, source_lines, line_numbers)


def _statement_placement_issues(
    body: list[ast.stmt],
    source_lines: list[bytes],
    issues: _LineIssues,
) -> None:
    """Find statements preceded by non-whitespace on their physical line."""
    line: int
    line_numbers: set[int]
    statement: ast.stmt

    line_numbers = set()

    for statement in body:
        _statement_placement_visit(statement, source_lines, line_numbers)
    for line in sorted(line_numbers):
        issues.add(line, _Rule.STMT_BEG)


def _indentation(text: str) -> int:
    prefix: str

    prefix = text[: len(text) - len(text.lstrip(" \t\f"))]
    # Python resets the indentation column at a form feed.
    return len(prefix.rsplit("\f", 1)[-1].expandtabs(8))


def _finish_physical_line_group(
    end_line: int,
    previous_end: int,
    lines: list[str],
    used: set[int],
    groups: list[set[int]],
) -> int:
    first: int
    last: int

    if not used:
        return previous_end
    first, last = min(used), max(used)
    # Explicit continuation lines containing only a backslash have no
    # token of their own. Include them in the physical extent.
    while first > previous_end + 1 and lines[first - 2].strip() == "\\":
        first -= 1
    while last < end_line and lines[last].strip() == "\\":
        last += 1
    used.update(
        line
        for line in range(first, last + 1)
        if lines[line - 1].strip() == "\\"
    )
    groups.append(set(used))
    used.clear()
    return last


def _physical_line_issues(
    module: ast.Module,
    source: str,
    issues: _LineIssues,
    prefix_end: int | None = None,
) -> None:
    """Group physical lines by statement, header or decorator."""
    at_line_start: bool
    deep: set[int]
    deep_start_lines: set[int]
    findings: set[int]
    first: int
    group: set[int]
    groups: list[set[int]]
    incorrect_indentation: set[int]
    indent_widths: Counter[int]
    indents: list[str]
    limit: int
    line: int
    lines: list[str]
    node: ast.AST
    node_types: tuple[type[ast.stmt], ...]
    nodes: list[ast.AST]
    parent: str
    previous_end: int
    rule: _Rule
    simple_starts: set[tuple[int, int]]
    starts: set[tuple[int, int]]
    text: str
    token: tokenize.TokenInfo
    trailing: set[int]
    used: set[int]
    width: int
    node_types = (
        ast.AsyncFor,
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.ClassDef,
        ast.For,
        ast.FunctionDef,
        ast.If,
        ast.Match,
        ast.Try,
        ast.TryStar,
        ast.While,
        ast.With,
    )

    lines = source.split("\n")
    nodes = list(ast.walk(module))
    # AST columns are UTF-8 byte offsets; tokenize uses character offsets.
    starts = set()
    simple_starts = set()
    for node in nodes:
        if isinstance(node, ast.stmt):
            text = lines[node.lineno - 1]
            text = text.encode("utf-8")[: node.col_offset].decode("utf-8")
            starts.add((node.lineno, len(text)))
            if not isinstance(node, node_types):
                simple_starts.add((node.lineno, len(text)))
    groups = []
    used = set()
    previous_end = 0
    indents = [""]
    indent_widths = Counter()
    incorrect_indentation = set()
    deep_start_lines = set()
    at_line_start = True

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if prefix_end is not None and token.start[0] > prefix_end:
            previous_end = _finish_physical_line_group(
                prefix_end, previous_end, lines, used, groups
            )
            break
        if token.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            _finish_physical_line_group(
                min(token.start[0], len(lines)),
                previous_end,
                lines,
                used,
                groups,
            )
            previous_end = token.start[0]
            at_line_start = True
            continue
        if token.type == tokenize.INDENT:
            # Diagnose the new indentation step, not inherited errors.
            parent = indents[-1]
            indent_widths[
                _indentation(token.string) - _indentation(parent)
            ] += 1
            if token.string != parent + "    ":
                incorrect_indentation.add(token.start[0])
            indents.append(token.string)
            continue
        if token.type == tokenize.DEDENT:
            indents.pop()
            continue
        if token.type in (tokenize.NL, tokenize.COMMENT):
            continue
        if at_line_start:
            line = token.start[0]
            if lines[line - 1][: token.start[1]] != indents[-1]:
                incorrect_indentation.add(line)
            at_line_start = False
        # Inline suites share a logical line with their header; an AST
        # statement start separates the header from the first simple statement.
        if len(indents) > 5 and token.start in simple_starts:
            deep_start_lines.add(token.start[0])
        if token.start in starts:
            previous_end = _finish_physical_line_group(
                token.start[0] - 1, previous_end, lines, used, groups
            )
        used.update(range(token.start[0], token.end[0] + 1))
        if token.type == tokenize.OP and token.string == ";":
            previous_end = _finish_physical_line_group(
                token.end[0], previous_end, lines, used, groups
            )

    trailing = {
        line
        for line, text in enumerate(lines, 1)
        if text != text.rstrip() and (prefix_end is None or line <= prefix_end)
    }
    deep = set()

    # Infer the continuation width from suites; prefer smaller tied widths.
    if indent_widths:
        width = min(indent_widths, key=lambda n: (-indent_widths[n], n))
        for group in groups:
            first = min(group)
            limit = _indentation(lines[first - 1]) + 2 * width
            deep.update(
                line
                for line in group
                if _indentation(lines[line - 1]) >= limit
            )

    for rule, findings in (
        (_Rule.LINE_TW, trailing),
        (_Rule.LINE_IND, incorrect_indentation),
        (_Rule.LINE_CONT, deep),
        (_Rule.LINE_DEEP, deep_start_lines),
    ):
        for line in sorted(findings):
            issues.add(line, rule)

    # Recovered prefixes are not complete files: their EOF is synthetic.
    if prefix_end is None and source:
        if source.endswith("\n"):
            lines.pop()  # The split sentinel is not a physical line.
        else:
            issues.add(len(lines), _Rule.LINE_NL)
        for line in range(len(lines), 0, -1):
            if lines[line - 1].strip():
                break
            issues.add(line, _Rule.LINE_BL)


def _declaration_line(
    statement: ast.AnnAssign, locations: _SourceLocations
) -> int:
    # The colon establishes the annotation, even across a backslash.
    return locations.following(statement.target, {":"})


def _check_finals(
    body: list[ast.stmt],
    inherited_imports: set[str],
    locations: _SourceLocations,
    issues: _LineIssues,
    is_module: bool = False,
) -> tuple[set[int], set[str]]:
    collector: _FunctionAnnotations
    direct: set[int]
    finals: set[int]
    imports: set[str]
    line: int
    statement: ast.AnnAssign
    collector = _collect_annotations(body)
    imports = inherited_imports | collector.final_imports
    direct = {id(stmt) for stmt in body}
    finals = set()
    for statement in collector.annotations:
        if (
            is_module
            and id(statement) in direct
            and _is_module_all_statement(statement)
        ):
            continue
        if not _is_final_annotation(statement.annotation, imports):
            continue
        finals.add(id(statement))
        line = _declaration_line(statement, locations)
        if id(statement) not in direct:
            issues.add(line, _Rule.FIN_PLAC)
        if statement.value is None:
            issues.add(line, _Rule.FIN_VAL)
    return finals, imports


def _check_scope(
    node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    external_assignments: dict[str, int],
    finals: set[int],
    locations: _SourceLocations,
    issues: _LineIssues,
    dead_module_names: list[str] | None = None,
    in_class: bool = False,
) -> None:
    annotations: list[ast.AnnAssign]
    arg: ast.arg
    args: ast.arguments
    bare_declarations: list[ast.AnnAssign]
    binding_lines: dict[str, int]
    body: list[ast.stmt]
    declaration_lines: dict[str, int]
    declaration_names: list[str]
    declaration_nodes: set[int]
    declared: set[str]
    decorator: ast.expr
    duplicates: list[tuple[int, str]]
    exempt: set[str]
    facts: _FunctionBodyFacts
    final_names: set[str]
    findings: Iterator[tuple[int, str]]
    greatest: str
    index: int
    is_module: bool
    leading_decls: list[ast.AnnAssign]
    line: int
    locals_that_need_declarations: set[str]
    name: str
    ordering_body: list[ast.stmt]
    requires_positional_only: bool
    scope_end: int
    seen: set[str]
    start: int
    statement: ast.AnnAssign
    unnecessary: set[str]
    unnecessary_lines: list[tuple[int, str]]
    is_module = isinstance(node, ast.Module)
    body = (
        [stmt for stmt in node.body if not _is_module_all_statement(stmt)]
        if is_module
        else node.body
    )
    # Keep __all__ out of variable analysis, but not out of statement order.
    ordering_body = node.body if is_module else body
    start = (
        1 if ordering_body and _is_docstring_statement(ordering_body[0]) else 0
    )
    while start < len(ordering_body) and (
        isinstance(ordering_body[start], (ast.Import, ast.ImportFrom))
        or (is_module and _is_module_all_statement(ordering_body[start]))
    ):
        start += 1

    leading_decls = []
    index = start
    while index < len(ordering_body):
        if id(ordering_body[index]) in finals:
            break
        if _is_bare_name_declaration(ordering_body[index]):
            leading_decls.append(ordering_body[index])  # type: ignore[arg-type]
        elif is_module or not isinstance(ordering_body[index], ast.ClassDef):
            break
        index += 1

    declaration_nodes = {id(decl) for decl in leading_decls}
    declaration_names = [decl.target.id for decl in leading_decls]  # type: ignore[union-attr]
    declared = set(declaration_names)
    annotations = _function_annotations(body)
    final_names = {
        statement.target.id
        for statement in annotations
        if id(statement) in finals
        and isinstance(statement.target, ast.Name)
        and statement.simple
    }
    annotations = [stmt for stmt in annotations if id(stmt) not in finals]

    facts = _collect_body_facts(body, declaration_nodes, locations)
    if isinstance(node, ast.Module):
        exempt = {
            "__annotations__",
            "__builtins__",
            "__cached__",
            "__doc__",
            "__file__",
            "__loader__",
            "__name__",
            "__package__",
            "__path__",
            "__spec__",
        }
    else:
        exempt = _parameter_names(node) | facts.globals | facts.nonlocals
    locals_that_need_declarations = (
        (facts.bound | external_assignments.keys())
        - exempt
        - facts.typevar_bindings
        - final_names
    )

    if isinstance(node, ast.Module):
        _check_module_all(node.body, locations, issues)
    facts.import_issues(issues)
    _statement_placement_issues(node.body, locations.lines, issues)
    if dead_module_names:
        issues.names(
            _Rule.DEAD_NAME,
            ((locations.last_line, name) for name in dead_module_names),
        )
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = node.args
        findings = (
            (locations.parameter_end(arg), arg.arg)
            for arg in _unannotated_parameters(node)
        )
        issues.names(_Rule.FUNC_ARG, findings)
        greatest = ""
        for arg in args.kwonlyargs:
            if arg.arg < greatest:
                issues.add(
                    arg.lineno,
                    _Rule.FUNC_KWOR,
                )
            greatest = max(greatest, arg.arg)
        if node.decorator_list:
            decorator = node.decorator_list[-1]
            requires_positional_only = (
                isinstance(decorator, ast.Name)
                and decorator.id == "classmethod"
            )
        else:
            requires_positional_only = in_class
        if requires_positional_only and not node.args.posonlyargs:
            issues.add(
                locations.positional_only_end(node),
                _Rule.FUNC_POS,
            )

    # A bare annotation later in the body is itself evidence that the
    # declaration block is not at the beginning.
    bare_declarations = [
        statement
        for statement in annotations
        if _is_bare_name_declaration(statement)
        and isinstance(statement.target, ast.Name)
    ]

    findings = (
        (_declaration_line(statement, locations), statement.target.id)
        for statement in bare_declarations
        if id(statement) not in declaration_nodes
        and isinstance(statement.target, ast.Name)
    )
    issues.names(_Rule.PLAC_BEG, findings)
    greatest = ""
    declaration_lines = {}
    for statement in leading_decls:
        assert isinstance(statement.target, ast.Name)
        name = statement.target.id
        line = _declaration_line(statement, locations)
        if name < greatest:
            issues.add(line, _Rule.REQD_ORD)
        greatest = max(greatest, name)
        _first_line(declaration_lines, name, line)

    findings = (
        (max(declaration_lines[name], facts.non_variable_lines[name]), name)
        for name in declared & facts.non_variable_bindings
    )
    issues.names(_Rule.EXEM_IMP, findings)
    findings = (
        (max(declaration_lines[name], facts.exception_lines[name]), name)
        for name in declared & facts.exception_bindings
    )
    issues.names(_Rule.EXEM_EX, findings)

    seen = set()
    duplicates = []
    for statement in sorted(
        bare_declarations, key=lambda stmt: (stmt.lineno, stmt.col_offset)
    ):
        assert isinstance(statement.target, ast.Name)
        name = statement.target.id
        if name in seen:
            duplicates.append((_declaration_line(statement, locations), name))
        seen.add(name)
    issues.names(_Rule.REQD_DUP, iter(duplicates))

    binding_lines = facts.binding_lines.copy()
    for name, line in external_assignments.items():
        _first_line(binding_lines, name, line)
    findings = (
        (binding_lines[name], name)
        for name in locals_that_need_declarations - declared
    )
    issues.names(_Rule.REQD_MIS, findings)
    unnecessary = (
        declared
        - locals_that_need_declarations
        - facts.non_variable_bindings
        - facts.exception_bindings
    )
    scope_end = locations.scope_end(node)
    unnecessary_lines = []
    for name in unnecessary:
        if name in exempt:
            line = declaration_lines[name]
        elif name in facts.typevar_lines:
            line = max(declaration_lines[name], facts.typevar_lines[name])
        else:
            line = scope_end
        unnecessary_lines.append((line, name))
    issues.names(_Rule.EXEM_UN, iter(unnecessary_lines))

    # Explicitly reject annotation-with-assignment anywhere in the function
    # body when its target is a simple local name.
    findings = (
        (locations.following(statement.annotation, {"="}), statement.target.id)
        for statement in annotations
        if isinstance(statement.target, ast.Name)
        and statement.value is not None
        and statement.target.id not in exempt
    )
    issues.names(_Rule.REQD_VAL, findings)


def _external_assignments(
    module: ast.Module,
    locations: _SourceLocations,
) -> dict[int, dict[str, int]]:
    """Find global/nonlocal assignments belonging to an enclosing scope."""
    assignments: dict[int, dict[str, int]]
    assignments = {}
    _external_assignments_visit(
        node=module,
        enclosing=[],
        assignments=assignments,
        module=module,
        locations=locations,
    )
    return assignments


def _external_assignments_visit(
    *,
    assignments: dict[int, dict[str, int]],
    enclosing: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, set[str]]],
    locations: _SourceLocations,
    module: ast.Module,
    node: ast.AST,
) -> None:
    child: ast.AST
    child_enclosing: list[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef, set[str]]
    ]
    facts: _FunctionBodyFacts
    local_names: set[str]
    name: str
    outer: ast.FunctionDef | ast.AsyncFunctionDef

    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for child in ast.iter_child_nodes(node):
            _external_assignments_visit(
                node=child,
                enclosing=enclosing,
                assignments=assignments,
                module=module,
                locations=locations,
            )
        return
    facts = _collect_body_facts(node.body, set(), locations)
    for name in (facts.bound & facts.globals) - {"__all__"}:
        _first_line(
            assignments.setdefault(id(module), {}),
            name,
            facts.binding_lines[name],
        )
    for name in facts.bound & facts.nonlocals:
        for outer, local_names in reversed(enclosing):
            if name in local_names:
                _first_line(
                    assignments.setdefault(id(outer), {}),
                    name,
                    facts.binding_lines[name],
                )
                break
    local_names = facts.bound
    local_names |= _parameter_names(node)
    local_names |= {
        annotation.target.id
        for annotation in _function_annotations(node.body)
        if isinstance(annotation.target, ast.Name) and annotation.simple
    }
    local_names -= facts.globals
    local_names -= facts.nonlocals
    child_enclosing = [*enclosing, (node, local_names)]
    for child in ast.iter_child_nodes(node):
        _external_assignments_visit(
            node=child,
            enclosing=child_enclosing,
            assignments=assignments,
            module=module,
            locations=locations,
        )


class _FunctionChecker(ast.NodeVisitor):
    def __init__(
        self: Self, /, filename: str, source: str, ignore: frozenset[str]
    ) -> None:
        self.filename = filename
        self.source = source
        self.locations = _SourceLocations(source)
        self.issues = _LineIssues(ignore)
        self.external_assignments: dict[int, dict[str, int]] = {}
        self.in_class: bool = False
        self.final_imports: set[str] = set()

    def visit_Module(self: Self, /, node: ast.Module) -> None:
        finals: set[int]
        parameter_assignments: _ParameterAssignments
        parameter_assignments = _ParameterAssignments(self.locations)
        parameter_assignments.visit(node)
        parameter_assignments.report(self.issues, [])
        finals, self.final_imports = _check_finals(
            node.body,
            self.final_imports,
            self.locations,
            self.issues,
            is_module=True,
        )
        self.external_assignments = _external_assignments(node, self.locations)
        _physical_line_issues(
            node, self.source, self.issues, self.locations.prefix_end
        )
        _check_scope(
            node,
            self.external_assignments.get(id(node), {}),
            finals,
            self.locations,
            self.issues,
            None
            if self.locations.prefix_end is not None
            else _dead_module_names(node, self.source, self.filename),
        )
        self.generic_visit(node)

    def _visit_function(
        self: Self,
        /,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        final_imports: set[str]
        finals: set[int]
        in_class: bool
        statement: ast.stmt
        final_imports = self.final_imports
        finals, self.final_imports = _check_finals(
            node.body, final_imports, self.locations, self.issues
        )
        _check_scope(
            node,
            self.external_assignments.get(id(node), {}),
            finals,
            self.locations,
            self.issues,
            in_class=self.in_class,
        )
        # Check nested functions too, without otherwise confusing their scope
        # with this function's scope.
        in_class = self.in_class
        self.in_class = False
        for statement in node.body:
            self.visit(statement)
        self.in_class = in_class
        self.final_imports = final_imports

    def visit_FunctionDef(self: Self, /, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(
        self: Self, /, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_function(node)

    def visit_ClassDef(self: Self, /, node: ast.ClassDef) -> None:
        in_class: bool
        # Class-local imports are visible in the class body, not its methods.
        _check_finals(
            node.body, self.final_imports, self.locations, self.issues
        )
        _collect_body_facts(node.body, set(), self.locations).import_issues(
            self.issues
        )
        _statement_placement_issues(
            node.body, self.locations.lines, self.issues
        )
        in_class = self.in_class
        self.in_class = True
        self.generic_visit(node)
        self.in_class = in_class


def _complete_prefix(
    source: str, path: str, stop: int
) -> tuple[str, ast.Module] | None:
    """Close unfinished suites without adding evidence on real lines."""
    candidate: str
    first: tokenize.TokenInfo | None
    indents: list[str]
    last: tokenize.TokenInfo | None
    message: str
    padded_source: str
    result: tuple[str, ast.Module] | None
    statement: str
    suffix: str
    suffixes: list[str]
    token: tokenize.TokenInfo
    try:
        return source, ast.parse(source, filename=path)
    except SyntaxError as exc:
        message = exc.msg
    if not (
        message.startswith("expected an indented block")
        or message == "expected 'except' or 'finally' block"
    ):
        return None

    # A complete header can precede the error even if its body is missing.
    # Keep track of indentation before the tokenizer's artificial EOF dedents.
    indents = [""]
    first = None
    last = None
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.start[0] > stop:
            break
        if token.type == tokenize.INDENT:
            indents.append(token.string)
        elif token.type == tokenize.DEDENT:
            indents.pop()
        elif token.type == tokenize.NEWLINE:
            last, first = first, None
        elif token.type not in (tokenize.NL, tokenize.COMMENT):
            if first is None:
                first = token
    padded_source = source + "\n" * max(1, stop + 1 - source.count("\n"))
    if message.startswith("expected an indented block") and last is not None:
        statement = "case _: pass" if last.string == "match" else "pass"
        suffixes = [indents[-1] + "    " + statement + "\n"]
    else:
        suffixes = [indent + "finally: pass\n" for indent in indents[-2::-1]]
    for suffix in suffixes:
        candidate = padded_source + suffix
        try:
            return candidate, ast.parse(candidate, filename=path)
        except SyntaxError as exc:
            if (
                exc.msg != "expected 'except' or 'finally' block"
                or (exc.lineno or 0) <= stop
            ):
                continue
            # Completing an inner suite can expose an unfinished outer try.
            result = _complete_prefix(candidate, path, candidate.count("\n"))
            if result is not None:
                return result
    return None


def _next_real_token(
    lines: list[str], stop: int, error: SyntaxError, line: int, column: int
) -> tokenize.TokenInfo | None:
    token: tokenize.TokenInfo
    try:
        for token in tokenize.generate_tokens(
            io.StringIO("".join(lines[:stop])).readline
        ):
            if token.start < (line, column):
                continue
            if token.start > (stop, max(0, (error.offset or 1) - 1)):
                break
            if token.type not in (
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.COMMENT,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
            ):
                return token
    except (SyntaxError, tokenize.TokenError):
        pass
    return None


def _check_prefix(
    path: str, source: str, error: SyntaxError, ignore: frozenset[str]
) -> _LineIssues:
    """Recover prefix findings strictly before the syntax-error line."""
    before: str
    boundaries: list[tuple[int, int]]
    checker: _FunctionChecker
    column: int
    issues: _LineIssues
    line: int
    lines: list[str]
    prefix: str
    recovered: str
    result: tuple[str, ast.Module] | None
    stop: int
    text: str
    token: tokenize.TokenInfo
    tree: ast.Module
    stop = error.lineno or 1
    lines = io.StringIO(source).readlines()
    # Include the error line only through a completed statement boundary.
    before = "".join(lines[: stop - 1])
    if stop <= len(lines):
        before += lines[stop - 1][: max(0, (error.offset or 1) - 1)]
    boundaries = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(before).readline):
            if token.type == tokenize.NEWLINE and (
                token.end[0] < stop or token.string
            ):
                boundaries.append(token.end)
            elif token.type == tokenize.OP and token.string == ";":
                boundaries.append(token.end)
    except (SyntaxError, tokenize.TokenError):
        pass
    # The parser can locate an unexpected EOF at the end of a valid header
    # or try body. In that case the entire last physical line precedes it.
    if stop <= len(lines) and (error.offset or 1) > len(
        lines[stop - 1].rstrip("\n")
    ):
        boundaries.append((stop, len(lines[stop - 1])))
    for line, column in reversed(boundaries):
        prefix = "".join(lines[: line - 1]) + lines[line - 1][:column]
        if not prefix.endswith("\n"):
            prefix += "\n"
        # Put all synthetic tokens beyond the interruption, not just
        # beyond the last complete statement.
        prefix += "\n" * max(0, stop - prefix.count("\n"))
        result = _complete_prefix(prefix, path, stop)
        if result is None:
            continue
        recovered, tree = result
        checker = _FunctionChecker(path, recovered, ignore)
        checker.locations.prefix_end = line
        # Only the first real token after the recovered boundary is
        # needed to determine whether an earlier scope has ended.
        checker.locations.next_token = _next_real_token(
            lines, stop, error, line, column
        )
        # EOF-dependent findings are not established by truncation.
        checker.locations.last_line = max(
            stop + 1, checker.locations.last_line
        )
        checker.visit(tree)
        issues = checker.issues
        issues.by_line = {
            n: messages for n, messages in issues.by_line.items() if n < stop
        }
        break
    else:
        issues = _LineIssues(ignore)
    # Whitespace on physical lines is independent of AST recovery.
    for line, text in enumerate(lines[: stop - 1], 1):
        if text.rstrip("\n") != text.rstrip():
            issues.add(line, _Rule.LINE_TW)
    return issues


def check_file(
    path: str, *, ignore: collections_abc.Iterable[str] = ()
) -> list[FunctionViolation]:
    checker: _FunctionChecker
    ignored: frozenset[str]
    issues: _LineIssues
    rule: str
    source: str
    tree: ast.Module
    violations: list[FunctionViolation]

    ignored = frozenset(ignore)
    source = Path(path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=path)
        # Parsing alone does not reject every syntax error (e.g. return
        # outside a function). Validate without executing the source.
        compile(tree, path, "exec", dont_inherit=True)
        checker = _FunctionChecker(path, source, ignored)
        checker.visit(tree)
        issues = checker.issues
    except SyntaxError as exc:
        issues = _check_prefix(path, source, exc, ignored)
        violations = list(issues.violations(path))
        rule = "SYN-" + type(exc).__name__
        if not _is_ignored(rule, ignored):
            violations.append(
                FunctionViolation(path, exc.lineno or 1, rule, exc.msg)
            )
        return violations
    return list(issues.violations(path))


def scan(
    file: str,
    errmsg: str,
    *,
    ignore: collections_abc.Iterable[str] = (),
) -> Iterator[str]:
    line: str
    violation: FunctionViolation
    violations: list[FunctionViolation]

    violations = check_file(file, ignore=ignore)
    for violation in violations:
        line = errmsg.format(
            file=violation.file,
            line=violation.line,
            rule=violation.rule,
            desc=violation.desc,
        )
        yield line
