import argparse
import sys
from pathlib import Path

from simple_dat.simple_dat import SimpleDat


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a CLRMamePro-compatible DAT file from a folder of ROMs."
    )
    parser.add_argument("folder", type=Path, help="Folder to scan")
    parser.add_argument("-o", "--output", type=Path, help="Output DAT file (default: <folder>.dat)")
    args = parser.parse_args()

    if not args.folder.is_dir():
        print(f"Error: '{args.folder}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    output = args.output or Path(args.folder.name + ".dat")

    print(f"Scanning {args.folder} ...")
    dat = SimpleDat.generate(args.folder)
    output.write_text(dat, encoding="utf-8")
    print(f"Written to {output}")


if __name__ == "__main__":
    main()
