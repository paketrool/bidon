import argparse
import io
import pathlib
import sys

from slanglang.interpreter import BidonRuntimeError, BidonSyntaxError, run_source


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


def main() -> int:
    configure_windows_console_encoding()

    parser = argparse.ArgumentParser(description="Интерпретатор языка Бидон")
    parser.add_argument("file", help="Путь к .bidon файлу")
    args = parser.parse_args()

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
