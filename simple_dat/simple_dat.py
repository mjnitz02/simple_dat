import copy
import hashlib
import sys
import zipfile
import zlib
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET


class SimpleDat:
    @staticmethod
    def _crc32(data: bytes) -> str:
        return format(zlib.crc32(data) & 0xFFFFFFFF, "08x")

    @staticmethod
    def hashes(data: bytes) -> dict:
        return {
            "crc": SimpleDat._crc32(data),
            "md5": hashlib.md5(data).hexdigest(),
            "sha1": hashlib.sha1(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    @staticmethod
    def _add_rom(parent: ET.Element, name: str, size: int, h: dict) -> None:
        rom = ET.SubElement(parent, "rom")
        rom.set("name", name)
        rom.set("size", str(size))
        rom.set("crc", h["crc"])
        rom.set("md5", h["md5"])
        rom.set("sha1", h["sha1"])
        rom.set("sha256", h["sha256"])
        rom.set("status", "verified")

    @staticmethod
    def _add_game(root: ET.Element, name: str, roms: list[dict]) -> None:
        game = ET.SubElement(root, "game")
        game.set("name", name)
        ET.SubElement(game, "description").text = name
        for rom in roms:
            SimpleDat._add_rom(game, rom["name"], rom["size"], rom["hashes"])

    @staticmethod
    def process_file(file_path: Path) -> tuple[str, list[dict]]:
        data = file_path.read_bytes()
        return file_path.stem, [
            {
                "name": file_path.name,
                "size": len(data),
                "hashes": SimpleDat.hashes(data),
            }
        ]

    @staticmethod
    def process_zip(file_path: Path) -> tuple[str, list[dict]]:
        game_name = file_path.stem
        roms = []
        with zipfile.ZipFile(file_path) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                if info.is_dir():
                    continue
                data = zf.read(info.filename)
                roms.append(
                    {
                        "name": info.filename,
                        "size": info.file_size,
                        "hashes": SimpleDat.hashes(data),
                    }
                )
        return game_name, roms

    @staticmethod
    def process_folder(folder_path: Path) -> tuple[str, list[dict]]:
        game_name = folder_path.name
        roms = []
        for file_path in sorted(f for f in folder_path.iterdir() if f.is_file()):
            data = file_path.read_bytes()
            roms.append(
                {
                    "name": file_path.name,
                    "size": len(data),
                    "hashes": SimpleDat.hashes(data),
                }
            )
        return game_name, roms

    @staticmethod
    def generate(folder: Path) -> str:
        root = ET.Element("datafile")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set(
            "xsi:schemaLocation",
            "https://datomatic.no-intro.org/stuff "
            "https://datomatic.no-intro.org/stuff/schema_nointro_datfile_v3.xsd",
        )

        header = ET.SubElement(root, "header")
        ET.SubElement(header, "name").text = "PLACEHOLDER"
        ET.SubElement(header, "description").text = "PLACEHOLDER"
        ET.SubElement(header, "version").text = datetime.now().strftime("%Y%m%d-%H%M%S")
        ET.SubElement(header, "author").text = "Claude, SimpleDat"
        ET.SubElement(header, "homepage").text = "SimpleDat"
        clrmamepro = ET.SubElement(header, "clrmamepro")
        clrmamepro.set("forcenodump", "required")

        children = sorted(folder.iterdir(), key=lambda p: p.name)
        use_dirs = any(p.is_dir() for p in children)
        candidates = [p for p in children if p.is_dir()] if use_dirs else [p for p in children if p.is_file()]
        total = len(candidates)

        for i, child in enumerate(candidates, 1):
            print(f"[{i}/{total}] {child.name}", file=sys.stderr)
            try:
                if use_dirs:
                    name, roms = SimpleDat.process_folder(child)
                elif child.suffix.lower() == ".zip":
                    name, roms = SimpleDat.process_zip(child)
                else:
                    name, roms = SimpleDat.process_file(child)
            except Exception as e:
                print(f"Warning: skipping {child.name}: {e}", file=sys.stderr)
                continue

            if roms:
                SimpleDat._add_game(root, name, roms)

        ET.indent(root, space="\t")
        return '<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n"

    @staticmethod
    def _goes_to_split1(game_name: str) -> bool:
        if "(Japan)" not in game_name:
            return True
        return "(En)" in game_name or "(En," in game_name

    @staticmethod
    def split(dat_file: Path) -> tuple[str, str]:
        root = ET.parse(dat_file).getroot()
        header = root.find("header")

        def make_out() -> ET.Element:
            out = ET.Element("datafile")
            out.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
            out.set(
                "xsi:schemaLocation",
                "https://datomatic.no-intro.org/stuff "
                "https://datomatic.no-intro.org/stuff/schema_nointro_datfile_v3.xsd",
            )
            out.append(copy.deepcopy(header))
            return out

        out1, out2 = make_out(), make_out()

        for game in root.findall("game"):
            name = game.get("name", "")
            target = out1 if SimpleDat._goes_to_split1(name) else out2
            target.append(copy.deepcopy(game))

        def serialise(tree: ET.Element) -> str:
            ET.indent(tree, space="\t")
            return '<?xml version="1.0"?>\n' + ET.tostring(tree, encoding="unicode") + "\n"

        return serialise(out1), serialise(out2)

    @staticmethod
    def prune(folder: Path, dat_file: Path) -> tuple[str, int, int]:
        folder_stems = {f.stem for f in folder.iterdir() if f.is_file()}

        root = ET.parse(dat_file).getroot()

        out = ET.Element("datafile")
        out.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        out.set(
            "xsi:schemaLocation",
            "https://datomatic.no-intro.org/stuff "
            "https://datomatic.no-intro.org/stuff/schema_nointro_datfile_v3.xsd",
        )
        out.append(copy.deepcopy(root.find("header")))

        kept = removed = 0
        for game in root.findall("game"):
            if game.get("name", "") in folder_stems:
                out.append(copy.deepcopy(game))
                kept += 1
            else:
                removed += 1

        ET.indent(out, space="\t")
        return '<?xml version="1.0"?>\n' + ET.tostring(out, encoding="unicode") + "\n", kept, removed

    @staticmethod
    def merge(file1: Path, file2: Path) -> str:
        root1 = ET.parse(file1).getroot()
        root2 = ET.parse(file2).getroot()

        out = ET.Element("datafile")
        out.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        out.set(
            "xsi:schemaLocation",
            "https://datomatic.no-intro.org/stuff "
            "https://datomatic.no-intro.org/stuff/schema_nointro_datfile_v3.xsd",
        )

        out.append(copy.deepcopy(root1.find("header")))

        games = root1.findall("game") + root2.findall("game")
        games.sort(key=lambda g: g.get("name", "").casefold())
        seen = set()
        for game in games:
            name = game.get("name", "")
            if name in seen:
                continue
            seen.add(name)
            out.append(copy.deepcopy(game))

        ET.indent(out, space="\t")
        return '<?xml version="1.0"?>\n' + ET.tostring(out, encoding="unicode") + "\n"