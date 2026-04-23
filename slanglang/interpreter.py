from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, List, Optional


KEYWORDS = {
    "заведи": "KW_VAR",
    "если_чё": "KW_IF",
    "иначе": "KW_ELSE",
    "го_пока": "KW_WHILE",
    "го_по": "KW_FOR",
    "от": "KW_FROM",
    "до": "KW_TO",
    "флекс": "KW_FUNC",
    "верни": "KW_RETURN",
    "чекни": "KW_PRINT",
    "тру": "KW_TRUE",
    "фолс": "KW_FALSE",
}


TOKEN_REGEX = re.compile(
    r"""
    (?P<WS>\s+)
    |(?P<COMMENT>//[^\n]*)
    |(?P<NUMBER>\d+(?:\.\d+)?)
    |(?P<STRING>\"(?:\\.|[^\"\\])*\")
    |(?P<OP>==|!=|<=|>=|&&|\|\|)
    |(?P<SYM>[+\-*/%=<>(){},;!])
    |(?P<ID>[A-Za-z_А-Яа-яЁё][A-Za-z0-9_А-Яа-яЁё]*)
    |(?P<MISMATCH>.)
    """,
    re.VERBOSE,
)


@dataclass
class Token:
    kind: str
    value: str
    pos: int


class BidonSyntaxError(Exception):
    pass


class BidonRuntimeError(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value



def _console_print(value: Any) -> None:
    text = str(value)
    if sys.platform == "win32":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            written = ctypes.c_ulong(0)
            payload = text + "\n"
            ok = ctypes.windll.kernel32.WriteConsoleW(
                handle,
                payload,
                len(payload),
                ctypes.byref(written),
                None,
            )
            if ok:
                return
        except Exception:
            pass
    print(text)

class Environment:
    def __init__(self, parent: Optional["Environment"] = None):
        self.parent = parent
        self.values: dict[str, Any] = {}

    def define(self, name: str, value: Any) -> None:
        self.values[name] = value

    def set(self, name: str, value: Any) -> None:
        if name in self.values:
            self.values[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value)
            return
        raise BidonRuntimeError(f"Переменная '{name}' не заведена")

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise BidonRuntimeError(f"Переменная '{name}' не найдена")


class FunctionValue:
    def __init__(self, name: str, params: list[str], body: list[dict[str, Any]], closure: Environment):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure

    def call(self, interpreter: "Interpreter", args: list[Any]) -> Any:
        if len(args) != len(self.params):
            raise BidonRuntimeError(
                f"Флекс '{self.name}' ждет {len(self.params)} аргументов, но получил {len(args)}"
            )
        scope = Environment(self.closure)
        for param_name, arg_value in zip(self.params, args):
            scope.define(param_name, arg_value)

        try:
            interpreter.execute_block(self.body, scope)
        except ReturnSignal as signal:
            return signal.value
        return None


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> list[dict[str, Any]]:
        statements: list[dict[str, Any]] = []
        while not self._check("EOF"):
            statements.append(self._statement())
        return statements

    def _statement(self) -> dict[str, Any]:
        if self._match("KW_VAR"):
            name = self._consume("ID", "После 'заведи' нужно имя переменной").value
            self._consume_value("=", "После имени переменной нужен '='")
            expr = self._expression()
            self._consume_value(";", "В конце объявления нужен ';'")
            return {"type": "var_decl", "name": name, "expr": expr}

        if self._match("KW_PRINT"):
            expr = self._expression()
            self._consume_value(";", "После 'чекни' нужен ';'")
            return {"type": "print", "expr": expr}

        if self._match("KW_IF"):
            self._consume_value("(", "После 'если_чё' нужна '('")
            condition = self._expression()
            self._consume_value(")", "После условия нужна ')'")
            then_block = self._block()
            else_block = None
            if self._match("KW_ELSE"):
                else_block = self._block()
            return {"type": "if", "condition": condition, "then": then_block, "else": else_block}

        if self._match("KW_WHILE"):
            self._consume_value("(", "После 'го_пока' нужна '('")
            condition = self._expression()
            self._consume_value(")", "После условия нужна ')'")
            body = self._block()
            return {"type": "while", "condition": condition, "body": body}

        if self._match("KW_FOR"):
            var_name = self._consume("ID", "После 'го_по' нужно имя переменной").value
            self._consume("KW_FROM", "После имени в 'го_по' нужно 'от'")
            start_expr = self._expression()
            self._consume("KW_TO", "После 'от <expr>' нужно 'до'")
            end_expr = self._expression()
            body = self._block()
            return {
                "type": "for",
                "var": var_name,
                "start": start_expr,
                "end": end_expr,
                "body": body,
            }

        if self._match("KW_FUNC"):
            name = self._consume("ID", "После 'флекс' нужно имя функции").value
            self._consume_value("(", "После имени функции нужна '('")
            params: list[str] = []
            if not self._check_value(")"):
                while True:
                    params.append(self._consume("ID", "Имя параметра ожидалось").value)
                    if not self._match_value(","):
                        break
            self._consume_value(")", "Список параметров должен закрываться ')' ")
            body = self._block()
            return {"type": "func_def", "name": name, "params": params, "body": body}

        if self._match("KW_RETURN"):
            if self._check_value(";"):
                self._advance()
                return {"type": "return", "expr": None}
            expr = self._expression()
            self._consume_value(";", "После 'верни' нужен ';'")
            return {"type": "return", "expr": expr}

        if self._check("ID") and self._check_next_value("="):
            name = self._advance().value
            self._consume_value("=", "Ожидался '='")
            expr = self._expression()
            self._consume_value(";", "В конце присваивания нужен ';'")
            return {"type": "assign", "name": name, "expr": expr}

        expr = self._expression()
        self._consume_value(";", "После выражения нужен ';'")
        return {"type": "expr_stmt", "expr": expr}

    def _block(self) -> list[dict[str, Any]]:
        self._consume_value("{", "Ожидался блок '{ ... }'")
        statements: list[dict[str, Any]] = []
        while not self._check_value("}") and not self._check("EOF"):
            statements.append(self._statement())
        self._consume_value("}", "Блок не закрыт '}'")
        return statements

    def _expression(self) -> dict[str, Any]:
        return self._or()

    def _or(self) -> dict[str, Any]:
        expr = self._and()
        while self._match_value("||"):
            operator = self._previous().value
            right = self._and()
            expr = {"type": "binary", "op": operator, "left": expr, "right": right}
        return expr

    def _and(self) -> dict[str, Any]:
        expr = self._equality()
        while self._match_value("&&"):
            operator = self._previous().value
            right = self._equality()
            expr = {"type": "binary", "op": operator, "left": expr, "right": right}
        return expr

    def _equality(self) -> dict[str, Any]:
        expr = self._comparison()
        while self._match_value("==", "!="):
            operator = self._previous().value
            right = self._comparison()
            expr = {"type": "binary", "op": operator, "left": expr, "right": right}
        return expr

    def _comparison(self) -> dict[str, Any]:
        expr = self._term()
        while self._match_value("<", "<=", ">", ">="):
            operator = self._previous().value
            right = self._term()
            expr = {"type": "binary", "op": operator, "left": expr, "right": right}
        return expr

    def _term(self) -> dict[str, Any]:
        expr = self._factor()
        while self._match_value("+", "-"):
            operator = self._previous().value
            right = self._factor()
            expr = {"type": "binary", "op": operator, "left": expr, "right": right}
        return expr

    def _factor(self) -> dict[str, Any]:
        expr = self._unary()
        while self._match_value("*", "/", "%"):
            operator = self._previous().value
            right = self._unary()
            expr = {"type": "binary", "op": operator, "left": expr, "right": right}
        return expr

    def _unary(self) -> dict[str, Any]:
        if self._match_value("-", "!"):
            operator = self._previous().value
            right = self._unary()
            return {"type": "unary", "op": operator, "expr": right}
        return self._call()

    def _call(self) -> dict[str, Any]:
        expr = self._primary()
        while self._match_value("("):
            args: list[dict[str, Any]] = []
            if not self._check_value(")"):
                while True:
                    args.append(self._expression())
                    if not self._match_value(","):
                        break
            self._consume_value(")", "Список аргументов должен закрываться ')' ")
            expr = {"type": "call", "callee": expr, "args": args}
        return expr

    def _primary(self) -> dict[str, Any]:
        if self._match("NUMBER"):
            text = self._previous().value
            if "." in text:
                value: Any = float(text)
            else:
                value = int(text)
            return {"type": "literal", "value": value}

        if self._match("STRING"):
            raw = self._previous().value
            value = bytes(raw[1:-1], "utf-8").decode("unicode_escape")
            return {"type": "literal", "value": value}

        if self._match("KW_TRUE"):
            return {"type": "literal", "value": True}

        if self._match("KW_FALSE"):
            return {"type": "literal", "value": False}

        if self._match("ID"):
            return {"type": "variable", "name": self._previous().value}

        if self._match_value("("):
            expr = self._expression()
            self._consume_value(")", "Выражение в скобках не закрыто ')' ")
            return {"type": "group", "expr": expr}

        token = self._peek()
        raise BidonSyntaxError(f"Неожиданный токен '{token.value}' на позиции {token.pos}")

    def _match(self, *kinds: str) -> bool:
        for kind in kinds:
            if self._check(kind):
                self._advance()
                return True
        return False

    def _match_value(self, *values: str) -> bool:
        for value in values:
            if self._check_value(value):
                self._advance()
                return True
        return False

    def _consume(self, kind: str, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        raise BidonSyntaxError(message)

    def _consume_value(self, value: str, message: str) -> Token:
        if self._check_value(value):
            return self._advance()
        raise BidonSyntaxError(message)

    def _check(self, kind: str) -> bool:
        if self._is_at_end():
            return kind == "EOF"
        return self._peek().kind == kind

    def _check_value(self, value: str) -> bool:
        if self._is_at_end():
            return False
        return self._peek().value == value

    def _check_next_value(self, value: str) -> bool:
        if self.index + 1 >= len(self.tokens):
            return False
        return self.tokens[self.index + 1].value == value

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.index += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        return self._peek().kind == "EOF"

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _previous(self) -> Token:
        return self.tokens[self.index - 1]


class Interpreter:
    def __init__(self):
        self.globals = Environment()

    def run(self, program: list[dict[str, Any]]) -> None:
        self.execute_block(program, self.globals)

    def execute_block(self, statements: list[dict[str, Any]], scope: Environment) -> None:
        previous = getattr(self, "env", self.globals)
        self.env = scope
        try:
            for stmt in statements:
                self.execute(stmt)
        finally:
            self.env = previous

    def execute(self, stmt: dict[str, Any]) -> None:
        stmt_type = stmt["type"]

        if stmt_type == "var_decl":
            value = self.eval(stmt["expr"])
            self.env.define(stmt["name"], value)
            return

        if stmt_type == "assign":
            value = self.eval(stmt["expr"])
            self.env.set(stmt["name"], value)
            return

        if stmt_type == "print":
            value = self.eval(stmt["expr"])
            _console_print(value)
            return

        if stmt_type == "if":
            if self._is_truthy(self.eval(stmt["condition"])):
                self.execute_block(stmt["then"], Environment(self.env))
            elif stmt["else"] is not None:
                self.execute_block(stmt["else"], Environment(self.env))
            return

        if stmt_type == "while":
            while self._is_truthy(self.eval(stmt["condition"])):
                self.execute_block(stmt["body"], Environment(self.env))
            return

        if stmt_type == "for":
            start = int(self.eval(stmt["start"]))
            end = int(self.eval(stmt["end"]))
            step = 1 if start <= end else -1
            loop_scope = Environment(self.env)
            loop_scope.define(stmt["var"], start)
            current = start
            while (current <= end and step > 0) or (current >= end and step < 0):
                loop_scope.set(stmt["var"], current)
                self.execute_block(stmt["body"], loop_scope)
                current += step
            return

        if stmt_type == "func_def":
            fn = FunctionValue(stmt["name"], stmt["params"], stmt["body"], self.env)
            self.env.define(stmt["name"], fn)
            return

        if stmt_type == "return":
            value = None if stmt["expr"] is None else self.eval(stmt["expr"])
            raise ReturnSignal(value)

        if stmt_type == "expr_stmt":
            self.eval(stmt["expr"])
            return

        raise BidonRuntimeError(f"Неизвестный тип инструкции: {stmt_type}")

    def eval(self, expr: dict[str, Any]) -> Any:
        expr_type = expr["type"]

        if expr_type == "literal":
            return expr["value"]

        if expr_type == "variable":
            return self.env.get(expr["name"])

        if expr_type == "group":
            return self.eval(expr["expr"])

        if expr_type == "unary":
            value = self.eval(expr["expr"])
            op = expr["op"]
            if op == "-":
                return -value
            if op == "!":
                return not self._is_truthy(value)
            raise BidonRuntimeError(f"Неизвестный унарный оператор '{op}'")

        if expr_type == "binary":
            left = self.eval(expr["left"])
            right = self.eval(expr["right"])
            op = expr["op"]

            if op == "+":
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "%":
                return left % right
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
            if op == "&&":
                return self._is_truthy(left) and self._is_truthy(right)
            if op == "||":
                return self._is_truthy(left) or self._is_truthy(right)

            raise BidonRuntimeError(f"Неизвестный бинарный оператор '{op}'")

        if expr_type == "call":
            callee = self.eval(expr["callee"])
            args = [self.eval(a) for a in expr["args"]]
            if not isinstance(callee, FunctionValue):
                raise BidonRuntimeError("Вызвать можно только флекс")
            return callee.call(self, args)

        raise BidonRuntimeError(f"Неизвестный тип выражения: {expr_type}")

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        return bool(value)


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    for match in TOKEN_REGEX.finditer(source):
        kind = match.lastgroup
        assert kind is not None
        value = match.group()
        pos = match.start()

        if kind in {"WS", "COMMENT"}:
            continue

        if kind == "MISMATCH":
            raise BidonSyntaxError(f"Неожиданный символ '{value}' на позиции {pos}")

        if kind == "ID":
            token_kind = KEYWORDS.get(value, "ID")
            tokens.append(Token(token_kind, value, pos))
            continue

        if kind == "OP" or kind == "SYM":
            tokens.append(Token("SYMBOL", value, pos))
            continue

        tokens.append(Token(kind, value, pos))

    tokens.append(Token("EOF", "", len(source)))
    return tokens


def parse(source: str) -> list[dict[str, Any]]:
    tokens = tokenize(source)
    parser = Parser(tokens)
    return parser.parse_program()


def run_source(source: str) -> None:
    program = parse(source)
    interpreter = Interpreter()
    interpreter.run(program)

