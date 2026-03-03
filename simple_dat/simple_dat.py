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

        for file_path in sorted(f for f in folder.iterdir() if f.is_file()):
            try:
                if file_path.suffix.lower() == ".zip":
                    name, roms = SimpleDat.process_zip(file_path)
                else:
                    name, roms = SimpleDat.process_file(file_path)
            except Exception as e:
                print(f"Warning: skipping {file_path.name}: {e}", file=sys.stderr)
                continue

            if roms:
                SimpleDat._add_game(root, name, roms)

        ET.indent(root, space="\t")
        return '<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n"