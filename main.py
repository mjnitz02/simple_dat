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

    spl = subparsers.add_parser("split", help="Split a DAT file into two (non-Japan/English and Japan-only).")
    spl.add_argument("file", type=Path, help="DAT file to split")
    spl.add_argument("--output1", type=Path, help="Output for split 1 (default: split_1.dat)")
    spl.add_argument("--output2", type=Path, help="Output for split 2 (default: split_2.dat)")

    prn = subparsers.add_parser("prune", help="Remove games from a DAT that are not present in a folder.")
    prn.add_argument("folder", type=Path, help="Folder to scan for files")
    prn.add_argument("file", type=Path, help="DAT file to prune")
    prn.add_argument("-o", "--output", type=Path, help="Output DAT file (default: overwrites input)")

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
        output = args.output or Path(args.file1.name)
        print(f"Merging {args.file1} + {args.file2} ...")
        dat = SimpleDat.merge(args.file1, args.file2)
        output.write_text(dat, encoding="utf-8")
        print(f"Written to {output}")
        return

    elif args.command == "prune":
        if not args.folder.is_dir():
            print(f"Error: '{args.folder}' is not a directory.", file=sys.stderr)
            sys.exit(1)
        if not args.file.is_file():
            print(f"Error: '{args.file}' is not a file.", file=sys.stderr)
            sys.exit(1)
        output = args.output or args.file
        print(f"Pruning {args.file} against {args.folder} ...")
        dat, kept, removed = SimpleDat.prune(args.folder, args.file)
        output.write_text(dat, encoding="utf-8")
        print(f"Kept {kept}, removed {removed}. Written to {output}")
        return

    elif args.command == "split":
        if not args.file.is_file():
            print(f"Error: '{args.file}' is not a file.", file=sys.stderr)
            sys.exit(1)
        out1 = args.output1 or Path(args.file.name)
        out2 = args.output2 or Path(args.file.stem + " (Japan).dat")
        print(f"Splitting {args.file} ...")
        dat1, dat2 = SimpleDat.split(args.file)
        out1.write_text(dat1, encoding="utf-8")
        out2.write_text(dat2, encoding="utf-8")
        print(f"Written to {out1} and {out2}")
        return

    output.write_text(dat, encoding="utf-8")
    print(f"Written to {output}")


if __name__ == "__main__":
    main()
