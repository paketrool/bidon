import argparse
import pathlib
import sys

from slanglang.interpreter import BidonRuntimeError, BidonSyntaxError, run_source


def configure_windows_console_encoding() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        # Use Windows OEM code page (e.g. cp866) to match classic PowerShell rendering.
        oem_codepage = int(ctypes.windll.kernel32.GetOEMCP())
        encoding = f"cp{oem_codepage}" if oem_codepage > 0 else "cp866"
    except Exception:
        encoding = "cp866"

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding=encoding, errors="replace")
        except Exception:
            pass


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

