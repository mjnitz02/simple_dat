import hashlib
import io
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

from simple_dat.simple_dat import SimpleDat


class TestHashes(unittest.TestCase):
    DATA = b"hello world"

    def test_crc(self):
        expected = format(zlib.crc32(self.DATA) & 0xFFFFFFFF, "08x")
        self.assertEqual(SimpleDat.hashes(self.DATA)["crc"], expected)

    def test_md5(self):
        self.assertEqual(SimpleDat.hashes(self.DATA)["md5"], hashlib.md5(self.DATA).hexdigest())

    def test_sha1(self):
        self.assertEqual(SimpleDat.hashes(self.DATA)["sha1"], hashlib.sha1(self.DATA).hexdigest())

    def test_sha256(self):
        self.assertEqual(SimpleDat.hashes(self.DATA)["sha256"], hashlib.sha256(self.DATA).hexdigest())

    def test_returns_all_four_keys(self):
        self.assertEqual(set(SimpleDat.hashes(self.DATA).keys()), {"crc", "md5", "sha1", "sha256"})

    def test_empty_bytes(self):
        result = SimpleDat.hashes(b"")
        self.assertEqual(result["md5"], "d41d8cd98f00b204e9800998ecf8427e")
        self.assertEqual(result["crc"], "00000000")

    def test_known_crc(self):
        # CRC-32 of b"123456789" is 0xCBF43926
        self.assertEqual(SimpleDat.hashes(b"123456789")["crc"], "cbf43926")


class TestProcessFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, filename: str, data: bytes = b"rom data") -> Path:
        p = self.tmpdir / filename
        p.write_bytes(data)
        return p

    def test_game_name_is_stem(self):
        name, _ = SimpleDat.process_file(self._write("Sonic the Hedgehog.md"))
        self.assertEqual(name, "Sonic the Hedgehog")

    def test_game_name_has_no_extension(self):
        name, _ = SimpleDat.process_file(self._write("Game.sfc"))
        self.assertNotIn(".", name)

    def test_returns_single_rom(self):
        _, roms = SimpleDat.process_file(self._write("Game.sfc"))
        self.assertEqual(len(roms), 1)

    def test_rom_name_includes_extension(self):
        _, roms = SimpleDat.process_file(self._write("Game.sfc"))
        self.assertEqual(roms[0]["name"], "Game.sfc")

    def test_rom_size(self):
        data = b"x" * 512
        _, roms = SimpleDat.process_file(self._write("Game.rom", data))
        self.assertEqual(roms[0]["size"], 512)

    def test_rom_hashes_correct(self):
        data = b"test content"
        _, roms = SimpleDat.process_file(self._write("Game.rom", data))
        self.assertEqual(roms[0]["hashes"], SimpleDat.hashes(data))

    def test_rom_hashes_keys_present(self):
        _, roms = SimpleDat.process_file(self._write("Game.rom"))
        self.assertEqual(set(roms[0]["hashes"].keys()), {"crc", "md5", "sha1", "sha256"})


class TestProcessZip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_zip(self, zip_name: str, files: dict) -> Path:
        path = self.tmpdir / zip_name
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in files.items():
                zf.writestr(name, data)
        return path

    def test_game_name_is_zip_stem(self):
        path = self._make_zip("Game Pack.zip", {"A.gb": b"a"})
        name, _ = SimpleDat.process_zip(path)
        self.assertEqual(name, "Game Pack")

    def test_game_name_has_no_extension(self):
        path = self._make_zip("Game.zip", {"A.gb": b"a"})
        name, _ = SimpleDat.process_zip(path)
        self.assertNotIn(".zip", name)

    def test_rom_count_matches_file_count(self):
        path = self._make_zip("Pack.zip", {"A.gb": b"a", "B.gb": b"b", "C.gb": b"c"})
        _, roms = SimpleDat.process_zip(path)
        self.assertEqual(len(roms), 3)

    def test_roms_sorted_alphabetically(self):
        path = self._make_zip("Pack.zip", {"C.gb": b"c", "A.gb": b"a", "B.gb": b"b"})
        _, roms = SimpleDat.process_zip(path)
        self.assertEqual([r["name"] for r in roms], ["A.gb", "B.gb", "C.gb"])

    def test_rom_size_is_uncompressed(self):
        data = b"x" * 1024
        path = self._make_zip("Pack.zip", {"Game.gb": data})
        _, roms = SimpleDat.process_zip(path)
        self.assertEqual(roms[0]["size"], 1024)

    def test_rom_hashes_correct(self):
        data = b"known content"
        path = self._make_zip("Pack.zip", {"Game.gb": data})
        _, roms = SimpleDat.process_zip(path)
        self.assertEqual(roms[0]["hashes"], SimpleDat.hashes(data))

    def test_directory_entries_skipped(self):
        path = self.tmpdir / "WithDir.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(zipfile.ZipInfo("subdir/"), b"")  # explicit dir entry
            zf.writestr("subdir/Game.gb", b"data")
        _, roms = SimpleDat.process_zip(path)
        self.assertEqual(len(roms), 1)
        self.assertEqual(roms[0]["name"], "subdir/Game.gb")

    def test_rom_hashes_keys_present(self):
        path = self._make_zip("Pack.zip", {"Game.gb": b"data"})
        _, roms = SimpleDat.process_zip(path)
        self.assertEqual(set(roms[0]["hashes"].keys()), {"crc", "md5", "sha1", "sha256"})


class TestProcessFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_folder(self, folder_name: str, files: dict) -> Path:
        path = self.tmpdir / folder_name
        path.mkdir()
        for name, data in files.items():
            (path / name).write_bytes(data)
        return path

    def test_game_name_is_folder_name(self):
        path = self._make_folder("Game Pack", {"A.gb": b"a"})
        name, _ = SimpleDat.process_folder(path)
        self.assertEqual(name, "Game Pack")

    def test_rom_count_matches_file_count(self):
        path = self._make_folder("Pack", {"A.gb": b"a", "B.gb": b"b", "C.gb": b"c"})
        _, roms = SimpleDat.process_folder(path)
        self.assertEqual(len(roms), 3)

    def test_roms_sorted_alphabetically(self):
        path = self._make_folder("Pack", {"C.gb": b"c", "A.gb": b"a", "B.gb": b"b"})
        _, roms = SimpleDat.process_folder(path)
        self.assertEqual([r["name"] for r in roms], ["A.gb", "B.gb", "C.gb"])

    def test_rom_size(self):
        data = b"x" * 512
        path = self._make_folder("Pack", {"Game.gb": data})
        _, roms = SimpleDat.process_folder(path)
        self.assertEqual(roms[0]["size"], 512)

    def test_rom_hashes_correct(self):
        data = b"known content"
        path = self._make_folder("Pack", {"Game.gb": data})
        _, roms = SimpleDat.process_folder(path)
        self.assertEqual(roms[0]["hashes"], SimpleDat.hashes(data))

    def test_rom_hashes_keys_present(self):
        path = self._make_folder("Pack", {"Game.gb": b"data"})
        _, roms = SimpleDat.process_folder(path)
        self.assertEqual(set(roms[0]["hashes"].keys()), {"crc", "md5", "sha1", "sha256"})

    def test_empty_folder_returns_no_roms(self):
        path = self._make_folder("Empty", {})
        _, roms = SimpleDat.process_folder(path)
        self.assertEqual(roms, [])


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _parse(self, folder: Path = None) -> ET.Element:
        xml = SimpleDat.generate(folder or self.tmpdir)
        return ET.parse(io.StringIO(xml)).getroot()

    def test_starts_with_xml_declaration(self):
        xml = SimpleDat.generate(self.tmpdir)
        self.assertTrue(xml.startswith('<?xml version="1.0"?>'))

    def test_root_element_is_datafile(self):
        self.assertEqual(self._parse().tag, "datafile")

    def test_header_name_is_placeholder(self):
        self.assertEqual(self._parse().find("header/name").text, "PLACEHOLDER")

    def test_header_description_is_placeholder(self):
        self.assertEqual(self._parse().find("header/description").text, "PLACEHOLDER")

    def test_header_author(self):
        self.assertEqual(self._parse().find("header/author").text, "Claude, SimpleDat")

    def test_header_homepage(self):
        self.assertEqual(self._parse().find("header/homepage").text, "SimpleDat")

    def test_header_version_format(self):
        import re
        version = self._parse().find("header/version").text
        self.assertRegex(version, r"^\d{8}-\d{6}$")

    def test_clrmamepro_forcenodump(self):
        clrmamepro = self._parse().find("header/clrmamepro")
        self.assertIsNotNone(clrmamepro)
        self.assertEqual(clrmamepro.get("forcenodump"), "required")

    def test_plain_file_produces_one_game(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        self.assertEqual(len(self._parse().findall("game")), 1)

    def test_plain_file_game_name_is_stem(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        self.assertEqual(self._parse().find("game").get("name"), "Zelda")

    def test_game_has_no_id_attribute(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        self.assertIsNone(self._parse().find("game").get("id"))

    def test_game_has_no_cloneofid_attribute(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        self.assertIsNone(self._parse().find("game").get("cloneofid"))

    def test_description_matches_game_name(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        game = self._parse().find("game")
        self.assertEqual(game.find("description").text, game.get("name"))

    def test_plain_file_rom_name_has_extension(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        self.assertEqual(self._parse().find("game/rom").get("name"), "Zelda.sfc")

    def test_rom_status_is_verified(self):
        (self.tmpdir / "Zelda.sfc").write_bytes(b"data")
        self.assertEqual(self._parse().find("game/rom").get("status"), "verified")

    def test_rom_has_size(self):
        data = b"x" * 128
        (self.tmpdir / "Game.rom").write_bytes(data)
        self.assertEqual(self._parse().find("game/rom").get("size"), "128")

    def test_rom_has_all_hash_attributes(self):
        (self.tmpdir / "Game.rom").write_bytes(b"data")
        rom = self._parse().find("game/rom")
        for attr in ("crc", "md5", "sha1", "sha256"):
            self.assertIsNotNone(rom.get(attr), f"rom missing attribute: {attr}")

    def test_zip_produces_one_game(self):
        with zipfile.ZipFile(self.tmpdir / "Pack.zip", "w") as zf:
            zf.writestr("A.gb", b"a")
            zf.writestr("B.gb", b"b")
        self.assertEqual(len(self._parse().findall("game")), 1)

    def test_zip_game_name_is_zip_stem(self):
        with zipfile.ZipFile(self.tmpdir / "Game Pack.zip", "w") as zf:
            zf.writestr("A.gb", b"a")
        self.assertEqual(self._parse().find("game").get("name"), "Game Pack")

    def test_zip_produces_one_rom_per_entry(self):
        with zipfile.ZipFile(self.tmpdir / "Pack.zip", "w") as zf:
            zf.writestr("A.gb", b"a")
            zf.writestr("B.gb", b"b")
        self.assertEqual(len(self._parse().find("game").findall("rom")), 2)

    def test_games_sorted_alphabetically(self):
        for name in ("Zelda.sfc", "Mario.sfc", "Castlevania.sfc"):
            (self.tmpdir / name).write_bytes(b"data")
        names = [g.get("name") for g in self._parse().findall("game")]
        self.assertEqual(names, sorted(names))

    def test_corrupt_zip_skipped(self):
        (self.tmpdir / "good.sfc").write_bytes(b"good")
        (self.tmpdir / "bad.zip").write_bytes(b"not a zip at all")
        games = self._parse().findall("game")
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].get("name"), "good")

    def test_empty_folder_produces_no_games(self):
        self.assertEqual(self._parse().findall("game"), [])

    def test_subfolder_produces_one_game_per_folder(self):
        for name in ("Game A", "Game B"):
            d = self.tmpdir / name
            d.mkdir()
            (d / "rom.gb").write_bytes(b"data")
        self.assertEqual(len(self._parse().findall("game")), 2)

    def test_subfolder_game_name_is_folder_name(self):
        d = self.tmpdir / "Zelda (USA)"
        d.mkdir()
        (d / "rom.gb").write_bytes(b"data")
        self.assertEqual(self._parse().find("game").get("name"), "Zelda (USA)")

    def test_subfolder_roms_come_from_folder_contents(self):
        d = self.tmpdir / "Pack"
        d.mkdir()
        (d / "A.gb").write_bytes(b"a")
        (d / "B.gb").write_bytes(b"b")
        self.assertEqual(len(self._parse().find("game").findall("rom")), 2)

    def test_subfolder_rom_hashes_correct(self):
        data = b"known content"
        d = self.tmpdir / "Pack"
        d.mkdir()
        (d / "Game.gb").write_bytes(data)
        rom = self._parse().find("game/rom")
        self.assertEqual(rom.get("crc"), SimpleDat.hashes(data)["crc"])

    def test_subfolders_sorted_alphabetically(self):
        for name in ("Zelda", "Mario", "Castlevania"):
            d = self.tmpdir / name
            d.mkdir()
            (d / "rom.gb").write_bytes(b"data")
        names = [g.get("name") for g in self._parse().findall("game")]
        self.assertEqual(names, sorted(names))

    def test_empty_subfolder_produces_no_game(self):
        (self.tmpdir / "Empty").mkdir()
        self.assertEqual(self._parse().findall("game"), [])


class TestMerge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_dat(self, name: str, rom_files: list[str]) -> Path:
        """Generate a DAT from a temporary folder of empty ROM files."""
        folder = self.tmpdir / name
        folder.mkdir()
        for f in rom_files:
            (folder / f).write_bytes(b"data")
        dat_path = self.tmpdir / f"{name}.dat"
        dat_path.write_text(SimpleDat.generate(folder))
        return dat_path

    def _make_dat_with_header(self, filename: str, header_name: str, games: list[str]) -> Path:
        """Write a minimal DAT file with a specific header name for testing header selection."""
        path = self.tmpdir / filename
        root = ET.Element("datafile")
        header = ET.SubElement(root, "header")
        ET.SubElement(header, "name").text = header_name
        ET.SubElement(header, "description").text = header_name
        ET.SubElement(header, "version").text = "20260101-000000"
        ET.SubElement(header, "author").text = "Test"
        ET.SubElement(header, "homepage").text = "Test"
        clrmamepro = ET.SubElement(header, "clrmamepro")
        clrmamepro.set("forcenodump", "required")
        for game_name in games:
            game = ET.SubElement(root, "game")
            game.set("name", game_name)
            ET.SubElement(game, "description").text = game_name
            rom = ET.SubElement(game, "rom")
            rom.set("name", f"{game_name}.rom")
            rom.set("size", "0")
            rom.set("crc", "00000000")
            rom.set("md5", "d41d8cd98f00b204e9800998ecf8427e")
            rom.set("sha1", "da39a3ee5e6b4b0d3255bfef95601890afd80709")
            rom.set("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
            rom.set("status", "verified")
        ET.indent(root, space="\t")
        path.write_text('<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n")
        return path

    def _parse(self, dat1: Path, dat2: Path) -> ET.Element:
        return ET.parse(io.StringIO(SimpleDat.merge(dat1, dat2))).getroot()

    def test_header_taken_from_first_file(self):
        dat1 = self._make_dat_with_header("a.dat", "First Set", ["Zelda"])
        dat2 = self._make_dat_with_header("b.dat", "Second Set", ["Mario"])
        self.assertEqual(self._parse(dat1, dat2).find("header/name").text, "First Set")

    def test_header_not_taken_from_second_file(self):
        dat1 = self._make_dat_with_header("a.dat", "First Set", ["Zelda"])
        dat2 = self._make_dat_with_header("b.dat", "Second Set", ["Mario"])
        self.assertNotEqual(self._parse(dat1, dat2).find("header/name").text, "Second Set")

    def test_games_from_both_files_present(self):
        dat1 = self._make_dat("set1", ["Zelda.sfc"])
        dat2 = self._make_dat("set2", ["Mario.sfc"])
        names = {g.get("name") for g in self._parse(dat1, dat2).findall("game")}
        self.assertIn("Zelda", names)
        self.assertIn("Mario", names)

    def test_total_game_count(self):
        dat1 = self._make_dat("set1", ["Zelda.sfc", "Link.sfc"])
        dat2 = self._make_dat("set2", ["Mario.sfc"])
        self.assertEqual(len(self._parse(dat1, dat2).findall("game")), 3)

    def test_games_sorted_alphabetically(self):
        dat1 = self._make_dat("set1", ["Zelda.sfc", "Castlevania.sfc"])
        dat2 = self._make_dat("set2", ["Mario.sfc", "Aladdin.sfc"])
        names = [g.get("name") for g in self._parse(dat1, dat2).findall("game")]
        self.assertEqual(names, sorted(names, key=str.casefold))

    def test_sort_is_case_insensitive(self):
        dat1 = self._make_dat_with_header("a.dat", "A", ["mario"])
        dat2 = self._make_dat_with_header("b.dat", "B", ["Zelda"])
        names = [g.get("name") for g in self._parse(dat1, dat2).findall("game")]
        self.assertEqual(names, ["mario", "Zelda"])

    def test_rom_entries_preserved(self):
        dat1 = self._make_dat("set1", ["Zelda.sfc"])
        dat2 = self._make_dat("set2", ["Mario.sfc"])
        root = self._parse(dat1, dat2)
        for game in root.findall("game"):
            rom = game.find("rom")
            self.assertIsNotNone(rom)
            for attr in ("crc", "md5", "sha1", "sha256", "size", "status"):
                self.assertIsNotNone(rom.get(attr), f"rom in {game.get('name')} missing {attr}")

    def test_output_is_valid_xml(self):
        dat1 = self._make_dat("set1", ["Zelda.sfc"])
        dat2 = self._make_dat("set2", ["Mario.sfc"])
        xml = SimpleDat.merge(dat1, dat2)
        self.assertTrue(xml.startswith('<?xml version="1.0"?>'))
        # Should parse without error
        ET.parse(io.StringIO(xml))

    def test_empty_first_file(self):
        dat1 = self._make_dat("set1", [])
        dat2 = self._make_dat("set2", ["Mario.sfc"])
        names = {g.get("name") for g in self._parse(dat1, dat2).findall("game")}
        self.assertEqual(names, {"Mario"})

    def test_empty_second_file(self):
        dat1 = self._make_dat("set1", ["Zelda.sfc"])
        dat2 = self._make_dat("set2", [])
        names = {g.get("name") for g in self._parse(dat1, dat2).findall("game")}
        self.assertEqual(names, {"Zelda"})

    def test_duplicate_game_appears_once(self):
        dat1 = self._make_dat_with_header("a.dat", "A", ["Zelda", "Mario"])
        dat2 = self._make_dat_with_header("b.dat", "B", ["Zelda", "Sonic"])
        names = [g.get("name") for g in self._parse(dat1, dat2).findall("game")]
        self.assertEqual(names.count("Zelda"), 1)

    def test_duplicate_keeps_first_occurrence(self):
        dat1 = self._make_dat_with_header("a.dat", "A", ["Zelda"])
        # Give the duplicate in dat2 a distinguishable rom name via a custom dat
        path = self.tmpdir / "b.dat"
        root = ET.Element("datafile")
        header = ET.SubElement(root, "header")
        ET.SubElement(header, "name").text = "B"
        ET.SubElement(header, "description").text = "B"
        ET.SubElement(header, "version").text = "20260101-000000"
        ET.SubElement(header, "author").text = "Test"
        ET.SubElement(header, "homepage").text = "Test"
        ET.SubElement(header, "clrmamepro").set("forcenodump", "required")
        game = ET.SubElement(root, "game")
        game.set("name", "Zelda")
        ET.SubElement(game, "description").text = "Zelda"
        rom = ET.SubElement(game, "rom")
        rom.set("name", "Zelda_v2.rom")
        rom.set("size", "0")
        rom.set("crc", "ffffffff")
        rom.set("md5", "d41d8cd98f00b204e9800998ecf8427e")
        rom.set("sha1", "da39a3ee5e6b4b0d3255bfef95601890afd80709")
        rom.set("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        rom.set("status", "verified")
        ET.indent(root, space="\t")
        path.write_text('<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n")
        result = self._parse(dat1, path)
        zelda = result.find("game[@name='Zelda']")
        self.assertNotEqual(zelda.find("rom").get("crc"), "ffffffff")


class TestGoesToSplit1(unittest.TestCase):
    def test_non_japan_goes_to_split1(self):
        self.assertTrue(SimpleDat._goes_to_split1("Sonic the Hedgehog (USA)"))

    def test_non_japan_no_region_goes_to_split1(self):
        self.assertTrue(SimpleDat._goes_to_split1("Tetris"))

    def test_japan_english_paren_goes_to_split1(self):
        self.assertTrue(SimpleDat._goes_to_split1("Dragon Quest (Japan) (En)"))

    def test_japan_english_comma_goes_to_split1(self):
        self.assertTrue(SimpleDat._goes_to_split1("Final Fantasy (Japan) (En,Fr)"))

    def test_japan_only_goes_to_split2(self):
        self.assertFalse(SimpleDat._goes_to_split1("Dragon Quest (Japan)"))

    def test_japan_japanese_language_goes_to_split2(self):
        self.assertFalse(SimpleDat._goes_to_split1("Zelda no Densetsu (Japan) (Ja)"))

    def test_japan_other_language_goes_to_split2(self):
        self.assertFalse(SimpleDat._goes_to_split1("Game (Japan) (De)"))

    def test_japan_in_name_but_not_tag_goes_to_split1(self):
        # "Japan" appears in the title but not as the region tag
        self.assertTrue(SimpleDat._goes_to_split1("Japan Adventure (USA)"))


class TestSplit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_dat(self, filename: str, header_name: str, games: list[str]) -> Path:
        path = self.tmpdir / filename
        root = ET.Element("datafile")
        header = ET.SubElement(root, "header")
        ET.SubElement(header, "name").text = header_name
        ET.SubElement(header, "description").text = header_name
        ET.SubElement(header, "version").text = "20260101-000000"
        ET.SubElement(header, "author").text = "Test"
        ET.SubElement(header, "homepage").text = "Test"
        clrmamepro = ET.SubElement(header, "clrmamepro")
        clrmamepro.set("forcenodump", "required")
        for game_name in games:
            game = ET.SubElement(root, "game")
            game.set("name", game_name)
            ET.SubElement(game, "description").text = game_name
            rom = ET.SubElement(game, "rom")
            rom.set("name", f"{game_name}.rom")
            rom.set("size", "0")
            rom.set("crc", "00000000")
            rom.set("md5", "d41d8cd98f00b204e9800998ecf8427e")
            rom.set("sha1", "da39a3ee5e6b4b0d3255bfef95601890afd80709")
            rom.set("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
            rom.set("status", "verified")
        ET.indent(root, space="\t")
        path.write_text('<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n")
        return path

    def _parse_split(self, games: list[str]) -> tuple[ET.Element, ET.Element]:
        dat = self._make_dat("input.dat", "Test Set", games)
        xml1, xml2 = SimpleDat.split(dat)
        return ET.parse(io.StringIO(xml1)).getroot(), ET.parse(io.StringIO(xml2)).getroot()

    def test_both_outputs_are_valid_xml(self):
        dat = self._make_dat("input.dat", "Test Set", ["Sonic (USA)", "Dragon Quest (Japan)"])
        xml1, xml2 = SimpleDat.split(dat)
        self.assertTrue(xml1.startswith('<?xml version="1.0"?>'))
        self.assertTrue(xml2.startswith('<?xml version="1.0"?>'))
        ET.parse(io.StringIO(xml1))
        ET.parse(io.StringIO(xml2))

    def test_headers_are_identical(self):
        root1, root2 = self._parse_split(["Sonic (USA)", "Dragon Quest (Japan)"])
        self.assertEqual(
            ET.tostring(root1.find("header")),
            ET.tostring(root2.find("header")),
        )

    def test_header_name_preserved(self):
        root1, _ = self._parse_split(["Sonic (USA)"])
        self.assertEqual(root1.find("header/name").text, "Test Set")

    def test_non_japan_game_in_split1(self):
        root1, _ = self._parse_split(["Sonic (USA)", "Dragon Quest (Japan)"])
        names = {g.get("name") for g in root1.findall("game")}
        self.assertIn("Sonic (USA)", names)

    def test_non_japan_game_not_in_split2(self):
        _, root2 = self._parse_split(["Sonic (USA)", "Dragon Quest (Japan)"])
        names = {g.get("name") for g in root2.findall("game")}
        self.assertNotIn("Sonic (USA)", names)

    def test_japan_only_game_in_split2(self):
        _, root2 = self._parse_split(["Sonic (USA)", "Dragon Quest (Japan)"])
        names = {g.get("name") for g in root2.findall("game")}
        self.assertIn("Dragon Quest (Japan)", names)

    def test_japan_only_game_not_in_split1(self):
        root1, _ = self._parse_split(["Sonic (USA)", "Dragon Quest (Japan)"])
        names = {g.get("name") for g in root1.findall("game")}
        self.assertNotIn("Dragon Quest (Japan)", names)

    def test_japan_english_paren_goes_to_split1(self):
        root1, root2 = self._parse_split(["Dragon Quest (Japan) (En)"])
        self.assertIn("Dragon Quest (Japan) (En)", {g.get("name") for g in root1.findall("game")})
        self.assertEqual(root2.findall("game"), [])

    def test_japan_english_comma_goes_to_split1(self):
        root1, root2 = self._parse_split(["Final Fantasy (Japan) (En,Fr)"])
        self.assertIn("Final Fantasy (Japan) (En,Fr)", {g.get("name") for g in root1.findall("game")})
        self.assertEqual(root2.findall("game"), [])

    def test_japan_other_language_goes_to_split2(self):
        root1, root2 = self._parse_split(["Game (Japan) (Ja)"])
        self.assertEqual(root1.findall("game"), [])
        self.assertIn("Game (Japan) (Ja)", {g.get("name") for g in root2.findall("game")})

    def test_all_games_preserved_across_both_splits(self):
        games = [
            "Sonic (USA)",
            "Dragon Quest (Japan)",
            "Final Fantasy (Japan) (En)",
            "Zelda (Europe)",
            "Castlevania (Japan) (Ja)",
        ]
        root1, root2 = self._parse_split(games)
        all_names = {g.get("name") for g in root1.findall("game")} | {g.get("name") for g in root2.findall("game")}
        self.assertEqual(all_names, set(games))

    def test_no_game_appears_in_both_splits(self):
        games = [
            "Sonic (USA)",
            "Dragon Quest (Japan)",
            "Final Fantasy (Japan) (En)",
        ]
        root1, root2 = self._parse_split(games)
        names1 = {g.get("name") for g in root1.findall("game")}
        names2 = {g.get("name") for g in root2.findall("game")}
        self.assertEqual(names1 & names2, set())

    def test_rom_entries_preserved_in_split1(self):
        root1, _ = self._parse_split(["Sonic (USA)"])
        rom = root1.find("game/rom")
        self.assertIsNotNone(rom)
        for attr in ("crc", "md5", "sha1", "sha256", "size", "status"):
            self.assertIsNotNone(rom.get(attr))

    def test_rom_entries_preserved_in_split2(self):
        _, root2 = self._parse_split(["Dragon Quest (Japan)"])
        rom = root2.find("game/rom")
        self.assertIsNotNone(rom)
        for attr in ("crc", "md5", "sha1", "sha256", "size", "status"):
            self.assertIsNotNone(rom.get(attr))

    def test_empty_dat_produces_no_games_in_either_split(self):
        root1, root2 = self._parse_split([])
        self.assertEqual(root1.findall("game"), [])
        self.assertEqual(root2.findall("game"), [])

    def test_all_non_japan_split2_is_empty(self):
        _, root2 = self._parse_split(["Sonic (USA)", "Mario (Europe)"])
        self.assertEqual(root2.findall("game"), [])

    def test_all_japan_only_split1_has_no_japan_only(self):
        root1, _ = self._parse_split(["Game A (Japan)", "Game B (Japan)"])
        self.assertEqual(root1.findall("game"), [])


class TestPrune(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _make_dat(self, games: list[str]) -> Path:
        path = self.tmpdir / "input.dat"
        root = ET.Element("datafile")
        header = ET.SubElement(root, "header")
        ET.SubElement(header, "name").text = "Test"
        ET.SubElement(header, "description").text = "Test"
        ET.SubElement(header, "version").text = "20260101-000000"
        ET.SubElement(header, "author").text = "Test"
        ET.SubElement(header, "homepage").text = "Test"
        clrmamepro = ET.SubElement(header, "clrmamepro")
        clrmamepro.set("forcenodump", "required")
        for game_name in games:
            game = ET.SubElement(root, "game")
            game.set("name", game_name)
            ET.SubElement(game, "description").text = game_name
            rom = ET.SubElement(game, "rom")
            rom.set("name", f"{game_name}.rom")
            rom.set("size", "0")
            rom.set("crc", "00000000")
            rom.set("md5", "d41d8cd98f00b204e9800998ecf8427e")
            rom.set("sha1", "da39a3ee5e6b4b0d3255bfef95601890afd80709")
            rom.set("sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
            rom.set("status", "verified")
        ET.indent(root, space="\t")
        path.write_text('<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n")
        return path

    def _make_folder(self, filenames: list[str]) -> Path:
        folder = self.tmpdir / "roms"
        folder.mkdir()
        for name in filenames:
            (folder / name).write_bytes(b"data")
        return folder

    def _prune(self, games: list[str], filenames: list[str]) -> tuple[ET.Element, int, int]:
        dat = self._make_dat(games)
        folder = self._make_folder(filenames)
        xml, kept, removed = SimpleDat.prune(folder, dat)
        return ET.parse(io.StringIO(xml)).getroot(), kept, removed

    def test_matching_game_kept(self):
        root, _, _ = self._prune(["Zelda"], ["Zelda.sfc"])
        self.assertEqual(len(root.findall("game")), 1)
        self.assertEqual(root.find("game").get("name"), "Zelda")

    def test_missing_game_removed(self):
        root, _, _ = self._prune(["Zelda", "Mario"], ["Zelda.sfc"])
        names = {g.get("name") for g in root.findall("game")}
        self.assertNotIn("Mario", names)

    def test_counts_kept_and_removed(self):
        _, kept, removed = self._prune(["Zelda", "Mario", "Sonic"], ["Zelda.sfc", "Sonic.sfc"])
        self.assertEqual(kept, 2)
        self.assertEqual(removed, 1)

    def test_empty_folder_removes_all(self):
        root, kept, removed = self._prune(["Zelda", "Mario"], [])
        self.assertEqual(root.findall("game"), [])
        self.assertEqual(kept, 0)
        self.assertEqual(removed, 2)

    def test_all_present_keeps_all(self):
        root, kept, removed = self._prune(["Zelda", "Mario"], ["Zelda.sfc", "Mario.sfc"])
        self.assertEqual(len(root.findall("game")), 2)
        self.assertEqual(kept, 2)
        self.assertEqual(removed, 0)

    def test_matching_is_by_stem_not_extension(self):
        root, _, _ = self._prune(["Zelda"], ["Zelda.zip"])
        self.assertEqual(len(root.findall("game")), 1)

    def test_header_preserved(self):
        root, _, _ = self._prune(["Zelda"], ["Zelda.sfc"])
        self.assertEqual(root.find("header/name").text, "Test")

    def test_output_is_valid_xml(self):
        dat = self._make_dat(["Zelda"])
        folder = self._make_folder(["Zelda.sfc"])
        xml, _, _ = SimpleDat.prune(folder, dat)
        self.assertTrue(xml.startswith('<?xml version="1.0"?>'))
        ET.parse(io.StringIO(xml))

    def test_rom_entries_preserved(self):
        root, _, _ = self._prune(["Zelda"], ["Zelda.sfc"])
        rom = root.find("game/rom")
        self.assertIsNotNone(rom)
        for attr in ("crc", "md5", "sha1", "sha256", "size", "status"):
            self.assertIsNotNone(rom.get(attr))

    def test_empty_dat_no_games(self):
        root, kept, removed = self._prune([], ["Zelda.sfc"])
        self.assertEqual(root.findall("game"), [])
        self.assertEqual(kept, 0)
        self.assertEqual(removed, 0)


if __name__ == "__main__":
    unittest.main()
