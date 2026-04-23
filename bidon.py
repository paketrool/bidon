import argparse
import os
import pathlib
import sys

from slanglang.interpreter import BidonRuntimeError, BidonSyntaxError, run_source


def configure_windows_utf8() -> None:
    if sys.platform != "win32":
        return

    # In classic Windows PowerShell, `chcp` is often required for visible UTF-8 output.
    try:
        os.system("chcp 65001 >NUL")
    except Exception:
        pass

    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    configure_windows_utf8()

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
