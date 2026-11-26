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
* every function parameter must have a type annotation;
* undecorated methods and functions directly decorated by ``@classmethod``
    must have a positional-only first parameter.

Imports may precede the declaration block in either scope, and module-level
``__all__`` is subject to its own separate rules.

Function parameters, ``global`` names, and ``nonlocal`` names are exempt from
local-variable declarations.
Nested functions/classes are checked independently and their bodies are not
treated as part of the enclosing function.

Each offending physical line produces exactly one report line.
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
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class FunctionViolation:
    file: str
    line: int
    desc: str


def _join_issues(issues: list[str]) -> str:
    return " ".join(issues)


class _LineIssues:
    """Collect physical-line issues, including named findings of one kind."""

    def __init__(self: Self, /) -> None:
        self.by_line: dict[int, list[str]] = {}

    def add(self: Self, /, line: int, issue: str) -> None:
        messages = self.by_line.setdefault(line, [])
        if issue + "!" not in messages:
            messages.append(issue + "!")

    def names(
        self: Self, /, issue: str, findings: Iterator[tuple[int, str]]
    ) -> None:
        grouped: dict[int, set[str]] = {}
        for line, name in findings:
            grouped.setdefault(line, set()).add(name)
        for line, names in grouped.items():
            self.add(line, issue + ": " + ", ".join(map(repr, sorted(names))))


class _SourceLocations:
    """Locate evidence in physical source order rather than AST walk order."""

    def __init__(self: Self, /, source: str) -> None:
        self.lines = source.encode("utf-8").split(b"\n")
        self.last_line = max(1, len(self.lines) - source.endswith("\n"))
        self.tokens = [
            token
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type
            not in (
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.COMMENT,
                tokenize.ENDMARKER,
            )
        ]
        self.positions = [token.start for token in self.tokens]
        self.prefix_end: int | None = None
        self.next_token: tokenize.TokenInfo | None = None

    def after(
        self: Self,
        /,
        node: ast.expr | ast.arg | ast.stmt,
    ) -> Iterator[tokenize.TokenInfo]:
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
        for token in self.after(node):
            if token.string in symbols:
                return token.start[0]
        return node.end_lineno or node.lineno

    def scope_end(self: Self, /, node: ast.Module | ast.stmt) -> int:
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
        assert node.type is not None
        tokens = self.after(node.type)
        for token in tokens:
            if token.string == "as":
                return next(tokens).start[0]
        return node.lineno

    def definition_name(
        self: Self,
        /,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> int:
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
        opened = False
        depth = 0
        # Ignore multiplication and unpacking within positional defaults or
        # annotations, even when the operator is at signature depth one.
        args = node.args
        last: ast.arg | ast.expr | None = None
        if args.defaults:
            last = args.defaults[-1]
        elif args.args:
            last = args.args[-1]
        boundary = (0, 0)
        if last is not None:
            line = last.end_lineno or last.lineno
            boundary = (
                line,
                len(
                    self.lines[line - 1][: last.end_col_offset].decode("utf-8")
                ),
            )
        start = bisect_left(self.positions, (node.lineno, 0))
        for i in range(start, len(self.tokens)):
            token = self.tokens[i]
            if not opened:
                if token.string == "(":
                    opened = True
                    depth = 1
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
    matches = [
        (index, stmt)
        for index, stmt in enumerate(body)
        if _is_module_all_statement(stmt)
    ]
    index = matches[0][0] if matches else len(body)
    for previous in body[:index]:
        if isinstance(previous, (ast.Import, ast.ImportFrom)) and not (
            isinstance(previous, ast.ImportFrom)
            and previous.level == 0
            and previous.module == "__future__"
        ):
            line = previous.lineno
            if isinstance(previous, ast.ImportFrom):
                start = bisect_left(locations.positions, (line, 0))
                for i in range(start, len(locations.tokens) - 1):
                    if locations.tokens[i].string == "from":
                        line = locations.tokens[i + 1].start[0]
                        break
            issues.add(line, "'__all__' must precede imports")
            break
    if not matches:
        issues.add(locations.last_line, "missing '__all__'")
        return
    _, stmt = matches[0]
    for _, repeated in matches[1:]:
        issues.add(repeated.lineno, "multiple '__all__' assignments")

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
        issues.add(line, "'__all__' must be annotated as 'list[str]'")
    value = (
        stmt.value if isinstance(stmt, (ast.AnnAssign, ast.Assign)) else None
    )
    if not isinstance(value, ast.List):
        line = (
            (value.end_lineno or value.lineno)
            if value is not None
            else (stmt.end_lineno or stmt.lineno)
        )
        issues.add(line, "'__all__' must be assigned a list literal")
        return
    greatest: str | None = None
    for item in value.elts:
        line = item.end_lineno or item.lineno
        if not isinstance(item, ast.Constant) or not isinstance(
            item.value, str
        ):
            issues.add(line, "'__all__' items must be string literals")
        elif greatest is not None and item.value < greatest:
            issues.add(line, "'__all__' items not in alphabetical order")
        else:
            greatest = item.value


class _FunctionAnnotations(ast.NodeVisitor):
    """Collect scope annotations without descending into nested scopes."""

    def __init__(self: Self, /) -> None:
        self.annotations: list[ast.AnnAssign] = []

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


def _function_annotations(body: list[ast.stmt]) -> list[ast.AnnAssign]:
    collector: _FunctionAnnotations
    statement: ast.stmt

    collector = _FunctionAnnotations()
    for statement in body:
        collector.visit(statement)
    return collector.annotations


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
        for line in sorted(self.wildcard_imports):
            issues.add(line, "wildcard imports are forbidden")
        issues.names(
            "'typing' imports available in 'collections.abc'",
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
        if isinstance(node.target, ast.Name):
            self._record(node.target.id, "read", node.target.lineno)
            self.visit(node.value)
            line = node.target.lineno
            if self.locations:
                line = self.locations.following(
                    node.target,
                    {
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
                    },
                )
            self._record(node.target.id, "bind", line)
        else:
            self.visit(node.target)
            self.visit(node.value)

    def visit_NamedExpr(self: Self, /, node: ast.NamedExpr) -> None:
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

    def visit_ExceptHandler(self: Self, /, node: ast.ExceptHandler) -> None:
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


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
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


def _statement_placement_issues(
    body: list[ast.stmt],
    source_lines: list[bytes],
    issues: _LineIssues,
) -> None:
    """Find statements preceded by non-whitespace on their physical line."""
    line_numbers: set[int]
    statement: ast.stmt

    line_numbers = set()

    def visit(node: ast.AST) -> None:
        child: ast.AST
        if isinstance(node, ast.stmt):
            if source_lines[node.lineno - 1][: node.col_offset].strip():
                line_numbers.add(node.lineno)
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in body:
        visit(statement)
    for line in sorted(line_numbers):
        issues.add(line, "simple statements not at beginning of physical line")


def _physical_line_issues(
    module: ast.Module,
    source: str,
    issues: _LineIssues,
    prefix_end: int | None = None,
) -> None:
    """Group physical lines by statement, header or decorator."""
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
    indent_widths: Counter[int] = Counter()
    incorrect_indentation = set()
    deep_start_lines = set()
    at_line_start = True

    def indentation(text: str) -> int:
        prefix: str

        prefix = text[: len(text) - len(text.lstrip(" \t\f"))]
        # Python resets the indentation column at a form feed.
        return len(prefix.rsplit("\f", 1)[-1].expandtabs(8))

    def finish(end_line: int) -> None:
        first: int
        last: int

        nonlocal previous_end
        if not used:
            return
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
        previous_end = last

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if prefix_end is not None and token.start[0] > prefix_end:
            finish(prefix_end)
            break
        if token.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            finish(min(token.start[0], len(lines)))
            previous_end = token.start[0]
            at_line_start = True
            continue
        if token.type == tokenize.INDENT:
            # Diagnose the new indentation step, not inherited errors.
            parent = indents[-1]
            indent_widths[indentation(token.string) - indentation(parent)] += 1
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
            finish(token.start[0] - 1)
        used.update(range(token.start[0], token.end[0] + 1))
        if token.type == tokenize.OP and token.string == ";":
            finish(token.end[0])

    trailing = {
        line
        for line, text in enumerate(lines, 1)
        if text != text.rstrip() and (prefix_end is None or line <= prefix_end)
    }
    deep: set[int] = set()

    # Infer the continuation width from suites; prefer smaller tied widths.
    if indent_widths:
        width = min(indent_widths, key=lambda n: (-indent_widths[n], n))
        for group in groups:
            first = min(group)
            limit = indentation(lines[first - 1]) + 2 * width
            for line in group:
                if indentation(lines[line - 1]) >= limit:
                    deep.add(line)

    for description, findings in (
        ("trailing whitespace on physical lines", trailing),
        ("indentation must be four spaces per level", incorrect_indentation),
        ("physical lines indented two or more levels deeper", deep),
        ("simple statements indented more than four levels", deep_start_lines),
    ):
        for line in sorted(findings):
            issues.add(line, description)


def _check_scope(
    node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    external_assignments: dict[str, int],
    locations: _SourceLocations,
    issues: _LineIssues,
    dead_module_names: list[str] | None = None,
    in_class: bool = False,
) -> None:
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

    leading_decls: list[ast.AnnAssign] = []
    index = start
    while index < len(ordering_body) and (
        _is_bare_name_declaration(ordering_body[index])
        or (not is_module and isinstance(ordering_body[index], ast.ClassDef))
    ):
        if _is_bare_name_declaration(ordering_body[index]):
            leading_decls.append(ordering_body[index])  # type: ignore[arg-type]
        index += 1

    declaration_nodes = {id(decl) for decl in leading_decls}
    declaration_names = [decl.target.id for decl in leading_decls]  # type: ignore[union-attr]
    declared = set(declaration_names)
    annotations = _function_annotations(body)

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
    )

    if isinstance(node, ast.Module):
        _check_module_all(node.body, locations, issues)
    facts.import_issues(issues)
    _statement_placement_issues(node.body, locations.lines, issues)
    if dead_module_names:
        issues.names(
            "dead module names",
            ((locations.last_line, name) for name in dead_module_names),
        )
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = node.args
        issues.names(
            "unannotated arguments",
            (
                (locations.parameter_end(arg), arg.arg)
                for arg in _unannotated_parameters(node)
            ),
        )
        greatest = ""
        for arg in args.kwonlyargs:
            if arg.arg < greatest:
                issues.add(
                    arg.lineno,
                    "keyword-only arguments not in alphabetical order",
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
                "first argument must be positional-only",
            )

    # A bare annotation later in the body is itself evidence that the
    # declaration block is not at the beginning.
    bare_declarations = [
        statement
        for statement in annotations
        if _is_bare_name_declaration(statement)
        and isinstance(statement.target, ast.Name)
    ]

    def declaration_line(statement: ast.AnnAssign) -> int:
        # The colon establishes the annotation, even across a backslash.
        return locations.following(statement.target, {":"})

    issues.names(
        "declarations not at beginning",
        (
            (declaration_line(statement), statement.target.id)
            for statement in bare_declarations
            if id(statement) not in declaration_nodes
            and isinstance(statement.target, ast.Name)
        ),
    )
    greatest = ""
    declaration_lines: dict[str, int] = {}
    for statement in leading_decls:
        assert isinstance(statement.target, ast.Name)
        name = statement.target.id
        line = declaration_line(statement)
        if name < greatest:
            issues.add(line, "declarations not in alphabetical order")
        greatest = max(greatest, name)
        _first_line(declaration_lines, name, line)

    issues.names(
        "declarations for 'def'/'class'/'import' names",
        (
            (
                max(declaration_lines[name], facts.non_variable_lines[name]),
                name,
            )
            for name in declared & facts.non_variable_bindings
        ),
    )
    issues.names(
        "declarations for 'except' names",
        (
            (max(declaration_lines[name], facts.exception_lines[name]), name)
            for name in declared & facts.exception_bindings
        ),
    )

    seen: set[str] = set()
    duplicates: list[tuple[int, str]] = []
    for statement in sorted(
        bare_declarations, key=lambda stmt: (stmt.lineno, stmt.col_offset)
    ):
        assert isinstance(statement.target, ast.Name)
        name = statement.target.id
        if name in seen:
            duplicates.append((declaration_line(statement), name))
        seen.add(name)
    issues.names("duplicate declarations", iter(duplicates))

    binding_lines = facts.binding_lines.copy()
    for name, line in external_assignments.items():
        _first_line(binding_lines, name, line)
    issues.names(
        "missing declarations",
        (
            (binding_lines[name], name)
            for name in locals_that_need_declarations - declared
        ),
    )
    unnecessary = (
        declared
        - locals_that_need_declarations
        - facts.non_variable_bindings
        - facts.exception_bindings
    )
    scope_end = locations.scope_end(node)
    unnecessary_lines: list[tuple[int, str]] = []
    for name in unnecessary:
        if name in exempt:
            line = declaration_lines[name]
        elif name in facts.typevar_lines:
            line = max(declaration_lines[name], facts.typevar_lines[name])
        else:
            line = scope_end
        unnecessary_lines.append((line, name))
    issues.names("unnecessary declarations", iter(unnecessary_lines))

    # Explicitly reject annotation-with-assignment anywhere in the function
    # body when its target is a simple local name.
    issues.names(
        "declaration assigns a value",
        (
            (
                locations.following(statement.annotation, {"="}),
                statement.target.id,
            )
            for statement in annotations
            if isinstance(statement.target, ast.Name)
            and statement.value is not None
            and statement.target.id not in exempt
        ),
    )


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
    module: ast.Module,
    node: ast.AST,
    locations: _SourceLocations,
) -> None:
    child: ast.AST
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
    enclosing = [*enclosing, (node, local_names)]
    for child in ast.iter_child_nodes(node):
        _external_assignments_visit(
            node=child,
            enclosing=enclosing,
            assignments=assignments,
            module=module,
            locations=locations,
        )


class _FunctionChecker(ast.NodeVisitor):
    def __init__(self: Self, /, filename: str, source: str) -> None:
        self.filename = filename
        self.source = source
        self.locations = _SourceLocations(source)
        self.issues = _LineIssues()
        self.external_assignments: dict[int, dict[str, int]] = {}
        self.in_class: bool = False

    def visit_Module(self: Self, /, node: ast.Module) -> None:
        self.external_assignments = _external_assignments(node, self.locations)
        _physical_line_issues(
            node, self.source, self.issues, self.locations.prefix_end
        )
        _check_scope(
            node,
            self.external_assignments.get(id(node), {}),
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
        _check_scope(
            node,
            self.external_assignments.get(id(node), {}),
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

    def visit_FunctionDef(self: Self, /, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(
        self: Self, /, node: ast.AsyncFunctionDef
    ) -> None:
        self._visit_function(node)

    def visit_ClassDef(self: Self, /, node: ast.ClassDef) -> None:
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
    source += "\n" * max(1, stop + 1 - source.count("\n"))
    if message.startswith("expected an indented block") and last is not None:
        statement = "case _: pass" if last.string == "match" else "pass"
        suffixes = [indents[-1] + "    " + statement + "\n"]
    else:
        suffixes = [indent + "finally: pass\n" for indent in indents[-2::-1]]
    for suffix in suffixes:
        candidate = source + suffix
        try:
            return candidate, ast.parse(candidate, filename=path)
        except SyntaxError as exc:
            if (
                exc.msg == "expected 'except' or 'finally' block"
                and (exc.lineno or 0) > stop
            ):
                # Completing an inner suite can expose an unfinished outer try.
                result = _complete_prefix(
                    candidate, path, candidate.count("\n")
                )
                if result is not None:
                    return result
    return None


def _check_prefix(path: str, source: str, error: SyntaxError) -> _LineIssues:
    """Check completed statements before the parser's reported error."""
    stop = error.lineno or 1
    lines = io.StringIO(source).readlines()
    # Include the error line only through a completed statement boundary.
    before = "".join(lines[: stop - 1])
    if stop <= len(lines):
        before += lines[stop - 1][: max(0, (error.offset or 1) - 1)]
    boundaries: list[tuple[int, int]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(before).readline):
            if token.type == tokenize.NEWLINE:
                line, column = token.end
                if line < stop or token.string:
                    boundaries.append((line, column))
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
        if result is not None:
            recovered, tree = result
            checker = _FunctionChecker(path, recovered)
            checker.locations.prefix_end = line
            # Only the first real token after the recovered boundary is
            # needed to determine whether an earlier scope has ended.
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
                        checker.locations.next_token = token
                        break
            except (SyntaxError, tokenize.TokenError):
                pass
            # EOF-dependent findings are not established by truncation.
            checker.locations.last_line = max(
                stop + 1, checker.locations.last_line
            )
            checker.visit(tree)
            issues = checker.issues
            issues.by_line = {
                n: messages
                for n, messages in issues.by_line.items()
                if n <= stop
            }
            break
    else:
        issues = _LineIssues()
    # Whitespace on physical lines is independent of AST recovery.
    for line, text in enumerate(lines[: stop - 1], 1):
        if text.rstrip("\n") != text.rstrip():
            messages = issues.by_line.setdefault(line, [])
            message = "trailing whitespace on physical lines!"
            if message not in messages:
                messages.insert(0, message)
    return issues


def check_file(path: str) -> list[FunctionViolation]:
    checker: _FunctionChecker
    source: str
    tree: ast.Module

    source = Path(path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=path)
        checker = _FunctionChecker(path, source)
        checker.visit(tree)
        issues = checker.issues
    except SyntaxError as exc:
        issues = _check_prefix(path, source, exc)
        issues.add(exc.lineno or 1, f"{type(exc).__name__}: {exc.msg}")
    return [
        FunctionViolation(path, line, _join_issues(messages))
        for line, messages in sorted(issues.by_line.items())
    ]


def scan(
    file: str,
    errmsg: str,
) -> Iterator[str]:
    line: str
    violation: FunctionViolation
    violations: list[FunctionViolation]

    violations = check_file(file)
    for violation in violations:
        line = errmsg.format(
            file=violation.file,
            line=violation.line,
            desc=violation.desc,
        )
        yield line
