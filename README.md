# SimpleDat

A simple CLI tool for generating and merging CLRMamePro-compatible DAT files. The output format follows the No-Intro XML schema.

## Commands

### `generate`

Scan a folder of ROM files and produce a DAT file.

```sh
uv run main.py generate <folder> [-o output.dat]
```

| Argument | Description |
|---|---|
| `folder` | Path to the folder containing ROM files |
| `-o`, `--output` | Output file path (default: `<folder name>.dat`) |

**Example:**

```sh
uv run main.py generate ~/roms/snes -o "Super Nintendo.dat"
```

### `merge`

Merge two existing No-Intro compatible DAT files into one. The header is taken from the first file, and all game entries from both files are combined and sorted alphabetically.

```sh
uv run main.py merge <file1.dat> <file2.dat> [-o output.dat]
```

| Argument | Description |
|---|---|
| `file1` | First DAT file — its header is used in the output |
| `file2` | Second DAT file |
| `-o`, `--output` | Output file path (default: `merged.dat`) |

**Example:**

```sh
uv run main.py merge "Nintendo - NES.dat" "Nintendo - Famicom.dat" -o "NES Merged.dat"
```

## How `generate` works

### Plain files

Each file is treated as a single game. The game name is the filename without its extension, and one `rom` entry is created for it.

```
Zelda.sfc  →  <game name="Zelda"> + <rom name="Zelda.sfc" .../>
```

### Zip files

A zip file is treated as a single game (named after the zip, without the `.zip` extension), with one `rom` entry per file inside the archive. The uncompressed size and hashes are used for each entry.

```
Game Pack.zip
  ├── Game A.gb  →  <rom name="Game A.gb" .../>
  └── Game B.gb  →  <rom name="Game B.gb" .../>
```

### ROM entries

Every `rom` element includes: `name`, `size`, `crc` (CRC-32), `md5`, `sha1`, `sha256`, and `status="verified"`.

### Header

The generated header uses `PLACEHOLDER` for `name` and `description` — fill these in after generation. The `version` is set to the current timestamp (`YYYYMMDD-HHMMSS`).

## Running tests

```sh
uv run pytest
```
