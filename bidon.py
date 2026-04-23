import argparse
import io
import pathlib
import sys

from slanglang.interpreter import (
    BidonRuntimeError,
    BidonSyntaxError,
    Interpreter,
    parse,
    run_source,
)


def _bind_stream_encoding(stream_name: str, encoding: str) -> None:
    stream = getattr(sys, stream_name)

    try:
        stream.reconfigure(encoding=encoding, errors="replace")
        return
    except Exception:
        pass

    try:
        buffer = stream.buffer
        wrapped = io.TextIOWrapper(
            buffer,
            encoding=encoding,
            errors="replace",
            line_buffering=True,
            write_through=True,
        )
        setattr(sys, stream_name, wrapped)
    except Exception:
        pass


def configure_windows_console_encoding() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        acp = int(ctypes.windll.kernel32.GetACP())
        encoding = f"cp{acp}" if acp > 0 else "cp1251"
    except Exception:
        encoding = "cp1251"

    _bind_stream_encoding("stdout", encoding)
    _bind_stream_encoding("stderr", encoding)


def _is_complete_chunk(text: str) -> bool:
    braces = 0
    in_string = False
    escaped = False

    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            braces += 1
        elif ch == "}":
            braces -= 1

    if in_string or braces > 0:
        return False

    stripped = text.strip()
    if not stripped:
        return False

    return stripped.endswith(";") or stripped.endswith("}")


def run_repl() -> int:
    print("Bidon REPL: пиши код на Бидоне. :help для подсказки, :exit для выхода")
    interpreter = Interpreter()
    lines: list[str] = []

    while True:
        prompt = "бидон> " if not lines else "... "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\n[Бидон] Ок, выходим")
            return 0

        command = line.strip()
        if not lines and command in {":exit", ":quit"}:
            return 0
        if not lines and command == ":help":
            print("Команды: :help, :exit")
            print("Пример: заведи имя = \"Коля\"; чекни \"прив, \" + имя;")
            continue
        if not lines and not command:
            continue

        lines.append(line)
        chunk = "\n".join(lines)

        if not _is_complete_chunk(chunk):
            continue

        try:
            program = parse(chunk)
            interpreter.run(program)
        except (BidonSyntaxError, BidonRuntimeError) as error:
            print(f"[Бидон фейл] {error}", file=sys.stderr)
        finally:
            lines.clear()


def main() -> int:
    configure_windows_console_encoding()

    parser = argparse.ArgumentParser(description="Интерпретатор языка Бидон")
    parser.add_argument("file", nargs="?", help="Путь к .bidon файлу")
    parser.add_argument("--repl", action="store_true", help="Запустить интерактивный режим")
    args = parser.parse_args()

    if args.repl or not args.file:
        return run_repl()

    file_path = pathlib.Path(args.file)
    source = file_path.read_text(encoding="utf-8-sig")

    try:
        run_source(source)
    except (BidonSyntaxError, BidonRuntimeError) as error:
        print(f"[Бидон фейл] {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
