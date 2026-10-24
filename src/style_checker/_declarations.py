#!/usr/bin/env python3
"""
Check module-level and function-local variable declaration style rules.

Rule implemented
----------------
At module level and inside every ``def`` or ``async def``:

* variables bound by assignment-like syntax in their scope must first be
    declared with a bare type annotation, e.g. ``count: int``;
* declarations must form one contiguous block at the beginning of the scope
    (an optional docstring may precede them);
* declarations must not assign a value;
* declaration names must be in alphabetical order;
* every function parameter must have a type annotation.

Imports may precede the declaration block in either scope, and module-level
``__all__`` is subject to its own separate rules.

Function parameters, ``global`` names, and ``nonlocal`` names are exempt from
local-variable declarations.
Nested functions/classes are checked independently and their bodies are not
treated as part of the enclosing function.

Each offending module or function produces exactly one report line.
"""

from __future__ import annotations

__all__: list[str] = [
    "scan",
]

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Self

ERRMSG_DEFAULT: str

ERRMSG_DEFAULT = "{file}:{line}: {desc}"


@dataclass(frozen=True)
class FunctionViolation:
    file: str
    line: int
    desc: str


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


def _check_module_all(body: list[ast.stmt]) -> list[str]:
    """Validate the special module-level ``__all__`` declaration."""
    index: int
    issues: list[str]
    matches: list[tuple[int, ast.stmt]]
    stmt: ast.stmt
    value: ast.expr | None

    matches = [
        (index, stmt)
        for index, stmt in enumerate(body)
        if _is_module_all_statement(stmt)
    ]
    if not matches:
        return ["missing __all__"]

    issues = []
    if len(matches) != 1:
        issues.append("multiple __all__ assignments")
    index, stmt = matches[0]
    if any(
        isinstance(previous, (ast.Import, ast.ImportFrom))
        and not (
            isinstance(previous, ast.ImportFrom)
            and previous.module == "__future__"
        )
        for previous in body[:index]
    ):
        issues.append("__all__ must precede imports")

    if not (
        isinstance(stmt, ast.AnnAssign)
        and isinstance(stmt.annotation, ast.Subscript)
        and isinstance(stmt.annotation.value, ast.Name)
        and stmt.annotation.value.id == "list"
        and isinstance(stmt.annotation.slice, ast.Name)
        and stmt.annotation.slice.id == "str"
    ):
        issues.append("__all__ must be annotated as list[str]")
    value = (
        stmt.value if isinstance(stmt, (ast.AnnAssign, ast.Assign)) else None
    )
    if not isinstance(value, ast.List):
        issues.append("__all__ must be assigned a list literal")
    elif any(
        not isinstance(item, ast.Constant) or not isinstance(item.value, str)
        for item in value.elts
    ):
        issues.append("__all__ items must be string literals")
    elif [item.value for item in value.elts] != sorted(
        item.value for item in value.elts
    ):
        issues.append("__all__ items not in alphabetical order")
    return issues


class _FunctionAnnotations(ast.NodeVisitor):
    """Collect scope annotations without descending into nested scopes."""

    def __init__(self: Self) -> None:
        self.annotations: list[ast.AnnAssign] = []

    def visit_AnnAssign(self: Self, node: ast.AnnAssign) -> None:
        self.annotations.append(node)

    def visit_FunctionDef(self: Self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self: Self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self: Self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self: Self, node: ast.Lambda) -> None:
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

    def __init__(self: Self) -> None:
        self.bound: set[str] = set()
        self.read: set[str] = set()
        self.first_kind: dict[str, str] = {}
        self.globals: set[str] = set()
        self.nonlocals: set[str] = set()
        self.non_variable_bindings: set[str] = set()
        self.exception_bindings: set[str] = set()

    def _record(self: Self, name: str, kind: str) -> None:
        if name not in self.first_kind:
            self.first_kind[name] = kind
        if kind == "bind":
            self.bound.add(name)
        elif kind == "read":
            self.read.add(name)

    def visit_Name(self: Self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record(node.id, "read")
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self._record(node.id, "bind")

    def visit_Import(self: Self, node: ast.Import) -> None:
        alias: ast.alias

        for alias in node.names:
            self.non_variable_bindings.add(
                alias.asname or alias.name.split(".", 1)[0]
            )

    def visit_ImportFrom(self: Self, node: ast.ImportFrom) -> None:
        alias: ast.alias

        for alias in node.names:
            if alias.name != "*":
                self.non_variable_bindings.add(alias.asname or alias.name)

    def visit_Assign(self: Self, node: ast.Assign) -> None:
        # Python evaluates the RHS before binding assignment targets.
        target: ast.expr

        self.visit(node.value)
        for target in node.targets:
            self.visit(target)

    def visit_AnnAssign(self: Self, node: ast.AnnAssign) -> None:
        # Evaluate annotation/value before treating the target as bound.
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
            self.visit(node.target)
        # A bare annotation is a declaration, not a runtime assignment.

    def visit_AugAssign(self: Self, node: ast.AugAssign) -> None:
        # ``x += y`` reads x before it writes x.
        if isinstance(node.target, ast.Name):
            self._record(node.target.id, "read")
            self.visit(node.value)
            self._record(node.target.id, "bind")
        else:
            self.visit(node.target)
            self.visit(node.value)

    def visit_NamedExpr(self: Self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self.visit(node.target)

    def visit_For(self: Self, node: ast.For | ast.AsyncFor) -> None:
        statement: ast.stmt

        self.visit(node.iter)
        self.visit(node.target)
        for statement in node.body:
            self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)

    def visit_AsyncFor(self: Self, node: ast.AsyncFor) -> None:
        self.visit_For(node)

    def visit_With(self: Self, node: ast.With | ast.AsyncWith) -> None:
        item: ast.withitem
        statement: ast.stmt

        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self.visit(item.optional_vars)
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncWith(self: Self, node: ast.AsyncWith) -> None:
        self.visit_With(node)

    def visit_ExceptHandler(self: Self, node: ast.ExceptHandler) -> None:
        statement: ast.stmt

        if node.type is not None:
            self.visit(node.type)
        if node.name is not None:
            # ``except ... as name`` is a temporary exception binding, not a
            # function-local variable governed by the declaration rule.
            self.exception_bindings.add(node.name)
        for statement in node.body:
            self.visit(statement)

    def visit_Global(self: Self, node: ast.Global) -> None:
        self.globals.update(node.names)

    def visit_Nonlocal(self: Self, node: ast.Nonlocal) -> None:
        self.nonlocals.update(node.names)

    def visit_FunctionDef(self: Self, node: ast.FunctionDef) -> None:
        # The nested function's name is not treated as a "variable" for this
        # rule, and its body belongs to a different function scope.
        self.non_variable_bindings.add(node.name)

    def visit_AsyncFunctionDef(self: Self, node: ast.AsyncFunctionDef) -> None:
        self.non_variable_bindings.add(node.name)

    def visit_ClassDef(self: Self, node: ast.ClassDef) -> None:
        self.non_variable_bindings.add(node.name)

    def visit_Lambda(self: Self, node: ast.Lambda) -> None:
        return

    def visit_comprehension(self: Self, node: ast.comprehension) -> None:
        # Comprehension iteration variables live in the comprehension's own
        # implicit scope in Python 3.
        condition: ast.expr

        self.visit(node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def visit_ListComp(self: Self, node: ast.ListComp) -> None:
        generator: ast.comprehension

        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator)

    def visit_SetComp(self: Self, node: ast.SetComp) -> None:
        generator: ast.comprehension

        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator)

    def visit_DictComp(self: Self, node: ast.DictComp) -> None:
        generator: ast.comprehension

        self.visit(node.key)
        self.visit(node.value)
        for generator in node.generators:
            self.visit(generator)

    def visit_GeneratorExp(self: Self, node: ast.GeneratorExp) -> None:
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


def _unannotated_parameter_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    args: ast.arguments
    parameters: list[ast.arg]

    args = node.args
    parameters = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg is not None:
        parameters.append(args.vararg)
    if args.kwarg is not None:
        parameters.append(args.kwarg)
    return {arg.arg for arg in parameters if arg.annotation is None}


def _collect_body_facts(
    body: list[ast.stmt],
    declaration_nodes: set[int],
) -> _FunctionBodyFacts:
    facts: _FunctionBodyFacts
    statement: ast.stmt

    facts = _FunctionBodyFacts()

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


def _check_scope(
    filename: str,
    node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef,
    external_assignments: set[str],
) -> FunctionViolation | None:
    annotations: list[ast.AnnAssign]
    assigned_declarations: set[str]
    body: list[ast.stmt]
    declaration_names: list[str]
    declaration_nodes: set[int]
    declared: set[str]
    direct_annotation_nodes: set[int]
    duplicates: list[str]
    exception_declarations: list[str]
    exempt: set[str]
    facts: _FunctionBodyFacts
    index: int
    is_module: bool
    issues: list[str]
    late_declarations: list[str]
    leading_decls: list[ast.AnnAssign]
    locals_that_need_declarations: set[str]
    missing: list[str]
    names_for_duplicate_check: list[str]
    nested_declaration_names: list[str]
    non_variable_declarations: list[str]
    ordering_body: list[ast.stmt]
    start: int
    statement: ast.AnnAssign
    unannotated_parameters: list[str]
    unnecessary: list[str]

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
    while index < len(ordering_body) and _is_bare_name_declaration(
        ordering_body[index]
    ):
        leading_decls.append(ordering_body[index])  # type: ignore[arg-type]
        index += 1

    declaration_nodes = {id(decl) for decl in leading_decls}
    declaration_names = [decl.target.id for decl in leading_decls]  # type: ignore[union-attr]
    declared = set(declaration_names)
    annotations = _function_annotations(body)
    direct_annotation_nodes = {
        id(statement)
        for statement in body
        if isinstance(statement, ast.AnnAssign)
    }

    facts = _collect_body_facts(body, declaration_nodes)
    if isinstance(node, ast.Module):
        exempt = set()
        unannotated_parameters = []
    else:
        exempt = _parameter_names(node) | facts.globals | facts.nonlocals
        unannotated_parameters = sorted(_unannotated_parameter_names(node))
    locals_that_need_declarations = (
        facts.bound | external_assignments
    ) - exempt

    issues = _check_module_all(node.body) if is_module else []
    if unannotated_parameters:
        issues.append(
            "unannotated arguments: " + ", ".join(unannotated_parameters)
        )

    # A bare annotation later in the body is itself evidence that the
    # declaration block is not at the beginning.
    late_declarations = []
    for statement in annotations:
        if id(statement) in declaration_nodes:
            continue
        if _is_bare_name_declaration(statement):
            assert isinstance(statement.target, ast.Name)
            late_declarations.append(statement.target.id)
    if late_declarations:
        issues.append(
            "declarations not at beginning: "
            + ", ".join(sorted(set(late_declarations)))
        )

    if declaration_names != sorted(declaration_names):
        issues.append("declarations not in alphabetical order")

    non_variable_declarations = sorted(declared & facts.non_variable_bindings)
    if non_variable_declarations:
        issues.append(
            "declarations for def/class/import names: "
            + ", ".join(non_variable_declarations)
        )

    exception_declarations = sorted(declared & facts.exception_bindings)
    if exception_declarations:
        issues.append(
            "declarations for except names: "
            + ", ".join(exception_declarations)
        )

    nested_declaration_names = [
        statement.target.id
        for statement in annotations
        if (
            id(statement) not in direct_annotation_nodes
            and _is_bare_name_declaration(statement)
            and isinstance(statement.target, ast.Name)
        )
    ]
    names_for_duplicate_check = declaration_names + nested_declaration_names
    duplicates = sorted(
        {
            name
            for name in names_for_duplicate_check
            if names_for_duplicate_check.count(name) > 1
        }
    )
    if duplicates:
        issues.append("duplicate declarations: " + ", ".join(duplicates))

    missing = sorted(locals_that_need_declarations - declared)
    if missing:
        issues.append("missing declarations: " + ", ".join(missing))

    unnecessary = sorted(
        declared
        - locals_that_need_declarations
        - facts.non_variable_bindings
        - facts.exception_bindings
    )
    if unnecessary:
        issues.append("unnecessary declarations: " + ", ".join(unnecessary))

    # Explicitly reject annotation-with-assignment anywhere in the function
    # body when its target is a simple local name.
    assigned_declarations = set()
    for statement in annotations:
        if (
            isinstance(statement.target, ast.Name)
            and statement.value is not None
            and statement.target.id not in exempt
        ):
            assigned_declarations.add(statement.target.id)
    if assigned_declarations:
        issues.append(
            "declaration assigns a value: "
            + ", ".join(sorted(assigned_declarations))
        )

    if not issues:
        return None

    return FunctionViolation(
        file=filename,
        line=1 if is_module else node.lineno,
        desc="; ".join(issues),
    )


def _external_assignments(module: ast.Module) -> dict[int, set[str]]:
    """Find global/nonlocal assignments belonging to an enclosing scope."""
    assignments: dict[int, set[str]]

    assignments = {}

    def visit(
        node: ast.AST,
        enclosing: list[
            tuple[ast.FunctionDef | ast.AsyncFunctionDef, set[str]]
        ],
    ) -> None:
        child: ast.AST
        facts: _FunctionBodyFacts
        local_names: set[str]
        name: str
        outer: ast.FunctionDef | ast.AsyncFunctionDef

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            facts = _collect_body_facts(node.body, set())
            assignments.setdefault(id(module), set()).update(
                (facts.bound & facts.globals) - {"__all__"}
            )
            for name in facts.bound & facts.nonlocals:
                for outer, local_names in reversed(enclosing):
                    if name in local_names:
                        assignments.setdefault(id(outer), set()).add(name)
                        break
            local_names = (
                (
                    facts.bound
                    | _parameter_names(node)
                    | {
                        annotation.target.id
                        for annotation in _function_annotations(node.body)
                        if isinstance(annotation.target, ast.Name)
                        and annotation.simple
                    }
                )
                - facts.globals
                - facts.nonlocals
            )
            enclosing = [*enclosing, (node, local_names)]
        for child in ast.iter_child_nodes(node):
            visit(child, enclosing)

    visit(module, [])
    return assignments


class _FunctionChecker(ast.NodeVisitor):
    def __init__(self: Self, filename: str) -> None:
        self.filename = filename
        self.violations: list[FunctionViolation] = []
        self.external_assignments: dict[int, set[str]] = {}

    def visit_Module(self: Self, node: ast.Module) -> None:
        violation: FunctionViolation | None

        self.external_assignments = _external_assignments(node)
        violation = _check_scope(
            self.filename, node, self.external_assignments.get(id(node), set())
        )
        if violation is not None:
            self.violations.append(violation)
        self.generic_visit(node)

    def _visit_function(
        self: Self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        statement: ast.stmt
        violation: FunctionViolation | None

        violation = _check_scope(
            self.filename, node, self.external_assignments.get(id(node), set())
        )
        if violation is not None:
            self.violations.append(violation)

        # Check nested functions too, without otherwise confusing their scope
        # with this function's scope.
        for statement in node.body:
            self.visit(statement)

    def visit_FunctionDef(self: Self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self: Self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)


def check_file(path: str) -> list[FunctionViolation]:
    checker: _FunctionChecker
    source: str
    tree: ast.Module

    source = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=path)
    checker = _FunctionChecker(path)
    checker.visit(tree)
    return checker.violations


def scan(
    file: str,
    errmsg: str,
) -> Iterator[str]:
    desc: str
    error_line: int
    line: str
    violation: FunctionViolation
    violations: list[FunctionViolation]

    violations = []
    try:
        violations.extend(check_file(file))
    except (OSError, UnicodeError, SyntaxError) as exc:
        desc = f"cannot analyze file: {exc}"
        error_line = getattr(exc, "lineno", None) or 1
        violations.append(
            FunctionViolation(file=file, line=error_line, desc=desc)
        )
    for violation in violations:
        try:
            line = errmsg.format(
                file=violation.file,
                line=violation.line,
                desc=violation.desc,
            )
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f"invalid --errmsg: {exc}") from exc
        yield line
