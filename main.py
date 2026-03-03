import argparse
import sys
from pathlib import Path

from simple_dat.simple_dat import SimpleDat


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate or merge CLRMamePro-compatible DAT files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="Generate a DAT file from a folder of ROMs.")
    gen.add_argument("folder", type=Path, help="Folder to scan")
    gen.add_argument("-o", "--output", type=Path, help="Output DAT file (default: <folder>.dat)")

    mrg = subparsers.add_parser("merge", help="Merge two DAT files into one.")
    mrg.add_argument("file1", type=Path, help="First DAT file (provides the header)")
    mrg.add_argument("file2", type=Path, help="Second DAT file")
    mrg.add_argument("-o", "--output", type=Path, help="Output DAT file (default: merged.dat)")

    args = parser.parse_args()

    if args.command == "generate":
        if not args.folder.is_dir():
            print(f"Error: '{args.folder}' is not a directory.", file=sys.stderr)
            sys.exit(1)
        output = args.output or Path(args.folder.name + ".dat")
        print(f"Scanning {args.folder} ...")
        dat = SimpleDat.generate(args.folder)

    elif args.command == "merge":
        for f in (args.file1, args.file2):
            if not f.is_file():
                print(f"Error: '{f}' is not a file.", file=sys.stderr)
                sys.exit(1)
        output = args.output or Path("merged.dat")
        print(f"Merging {args.file1} + {args.file2} ...")
        dat = SimpleDat.merge(args.file1, args.file2)

    output.write_text(dat, encoding="utf-8")
    print(f"Written to {output}")


if __name__ == "__main__":
    main()
