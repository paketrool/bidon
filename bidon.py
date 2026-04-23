import argparse
import pathlib
import sys

from slanglang.interpreter import BidonRuntimeError, BidonSyntaxError, run_source


def main() -> int:
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
