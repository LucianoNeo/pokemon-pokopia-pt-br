from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import struct
import sys
import tempfile
import threading
import urllib.request
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_VERSION = "2.5.9"
GAME_TITLE_ID = 0x0400A3A01EE4C000
GAME_TITLE_ID_HEX = f"{GAME_TITLE_ID:016X}"
NUP_UPDATE_VERSION = 655360
PACKAGE_NAME = "Pokemon-Pokopia-PT-BR-v2.5.9.zip"
PACKAGE_URL = (
    "https://github.com/LucianoNeo/pokemon-pokopia-pt-br/releases/download/"
    "v2.5.9/Pokemon-Pokopia-PT-BR-v2.5.9.zip"
)

ROMFS_FILES = (
    "LD_C0_R.BIN",
    "LI_C0_R.IDX",
    "motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb",
    "motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata",
)

# The index and asset sizes distinguish the two supported game updates.
VERSIONS = {
    "2.0.1": {
        "update_id": "655360",
        "nup_version": NUP_UPDATE_VERSION,
    },
}

NUP_MAGIC = b"NUP\x01"
NUP_TOC_MAGIC = b"TOC\x01"
NUP_HEADER = struct.Struct("<4sHHQQ32sQQII16s32s")
NUP_TOC_HEADER = struct.Struct("<4sIQQQQQ")
NUP_PACKAGE = struct.Struct("<QIIIIBBHIQI20x")
NUP_DIRECTORY = struct.Struct("<IIIIQ")
NUP_FILE = struct.Struct("<IIQQQ32sBBH12x")
NUP_NO_DIR = 0xFFFFFFFF
NUP_KIND_UPDATE = 1
NUP_EXTENT_ALIGNMENT = 16


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def read_nup_layout(path: Path) -> dict:
    """Read and structurally validate a NUP v1 container without unpacking its blobs."""
    file_size = path.stat().st_size
    with path.open("rb") as source:
        header_bytes = source.read(NUP_HEADER.size)
        if len(header_bytes) != NUP_HEADER.size:
            raise ValueError("O arquivo NUP está incompleto.")
        (magic, header_size, header_version, toc_offset, toc_size, toc_sha256,
         blob_offset, stored_file_size, package_count, flags, uuid, reserved) = \
            NUP_HEADER.unpack(header_bytes)
        if magic != NUP_MAGIC:
            raise ValueError("O arquivo não tem o cabeçalho NUP esperado.")
        if header_size < NUP_HEADER.size or toc_offset != header_size:
            raise ValueError("A versão do contêiner NUP não é compatível.")
        if stored_file_size != file_size:
            raise ValueError("O tamanho registrado no NUP não corresponde ao arquivo.")
        if flags != 0 or reserved != b"\0" * 32:
            raise ValueError("O cabeçalho NUP contém flags ou campos desconhecidos.")
        if package_count < 1 or toc_size < NUP_TOC_HEADER.size:
            raise ValueError("A tabela de conteúdo do NUP está incompleta.")
        if toc_offset + toc_size > file_size or blob_offset < toc_offset + toc_size:
            raise ValueError("Os offsets do NUP estão fora do arquivo.")
        if blob_offset % NUP_EXTENT_ALIGNMENT:
            raise ValueError("O início dos dados do NUP não está alinhado.")

        source.seek(toc_offset)
        toc = bytearray(source.read(toc_size))
        if len(toc) != toc_size or hashlib.sha256(toc).digest() != toc_sha256:
            raise ValueError("A tabela de conteúdo do NUP está corrompida.")

    (toc_magic, toc_package_count, dir_count, file_count,
     pool_offset, pool_size, _reserved_toc) = NUP_TOC_HEADER.unpack_from(toc)
    if toc_magic != NUP_TOC_MAGIC or toc_package_count != package_count:
        raise ValueError("A tabela de conteúdo do NUP não é compatível.")
    package_offset = NUP_TOC_HEADER.size
    directory_offset = package_offset + package_count * NUP_PACKAGE.size
    file_offset = directory_offset + dir_count * NUP_DIRECTORY.size
    children_offset = file_offset + file_count * NUP_FILE.size
    if (children_offset > pool_offset or pool_offset + pool_size > len(toc)
            or (pool_offset - children_offset) % 4):
        raise ValueError("Os índices internos do NUP estão fora dos limites.")

    pool = toc[pool_offset:pool_offset + pool_size]

    def pool_string(offset: int, length: int) -> bytes:
        if offset + length > len(pool):
            raise ValueError("O NUP contém um nome de arquivo inválido.")
        return bytes(pool[offset:offset + length])

    packages = []
    for index in range(package_count):
        offset = package_offset + index * NUP_PACKAGE.size
        (title_id, root_dir, exefs_dir, romfs_dir, version, kind, pkg_flags,
         reserved1, reserved2, meta_offset, meta_size) = NUP_PACKAGE.unpack_from(toc, offset)
        if reserved1 or reserved2:
            raise ValueError("O NUP contém campos de pacote desconhecidos.")
        packages.append({
            "index": index, "offset": offset, "title_id": title_id,
            "root_dir": root_dir, "exefs_dir": exefs_dir,
            "romfs_dir": romfs_dir, "version": version, "kind": kind,
            "flags": pkg_flags, "meta_offset": meta_offset,
            "meta_size": meta_size,
        })

    directories = []
    for index in range(dir_count):
        offset = directory_offset + index * NUP_DIRECTORY.size
        name_offset, name_length, first_child, child_count, reserved_dir = \
            NUP_DIRECTORY.unpack_from(toc, offset)
        if reserved_dir:
            raise ValueError("O NUP contém uma entrada de diretório inválida.")
        directories.append({
            "name": pool_string(name_offset, name_length),
            "first_child": first_child, "child_count": child_count,
        })

    files = []
    for index in range(file_count):
        offset = file_offset + index * NUP_FILE.size
        (name_offset, name_length, size, extent_offset, extent_size,
         digest, codec, codec_flags, reserved_file) = NUP_FILE.unpack_from(toc, offset)
        if codec not in (0, 1) or codec_flags or reserved_file:
            raise ValueError("O NUP contém um formato de arquivo não compatível.")
        if size and (extent_offset < blob_offset or extent_offset + extent_size > file_size):
            raise ValueError("Um arquivo do NUP aponta para fora do contêiner.")
        files.append({
            "name": pool_string(name_offset, name_length), "offset": offset,
            "size": size, "extent_offset": extent_offset,
            "extent_size": extent_size, "sha256": digest, "codec": codec,
        })

    children = list(struct.unpack_from(
        f"<{(pool_offset - children_offset) // 4}I", toc, children_offset
    ))
    for directory in directories:
        if directory["first_child"] + directory["child_count"] > len(children):
            raise ValueError("O NUP contém uma árvore de diretórios inválida.")

    return {
        "header": bytearray(header_bytes), "header_size": header_size,
        "header_version": header_version, "toc_offset": toc_offset,
        "toc_size": toc_size, "blob_offset": blob_offset,
        "file_size": file_size, "toc": toc, "packages": packages,
        "directories": directories, "files": files, "children": children,
        "dir_count": dir_count, "file_offset": file_offset,
    }


def nup_file_index(layout: dict, package: dict, relative: str) -> int:
    """Resolve a file below a package's declared RomFS directory."""
    current = package["romfs_dir"]
    if current == NUP_NO_DIR or current >= layout["dir_count"]:
        raise ValueError("O pacote NUP não contém RomFS.")
    parts = [part for part in relative.replace("\\", "/").split("/") if part]
    for part_index, part in enumerate(parts):
        directory = layout["directories"][current]
        matches = []
        for slot in range(directory["first_child"],
                          directory["first_child"] + directory["child_count"]):
            node = layout["children"][slot]
            if node < layout["dir_count"]:
                name = layout["directories"][node]["name"]
                is_dir = True
                node_index = node
            else:
                node_index = node - layout["dir_count"]
                if node_index >= len(layout["files"]):
                    raise ValueError("O NUP contém uma referência inválida na árvore.")
                name = layout["files"][node_index]["name"]
                is_dir = False
            if name.decode("utf-8", "replace").casefold() == part.casefold():
                matches.append((is_dir, node_index))
        if len(matches) != 1:
            raise ValueError(f"O NUP não contém um caminho único para {relative}.")
        is_dir, node_index = matches[0]
        if part_index < len(parts) - 1:
            if not is_dir:
                raise ValueError(f"O NUP contém um caminho incompleto para {relative}.")
            current = node_index
        elif is_dir:
            raise ValueError(f"O NUP aponta para uma pasta no lugar do arquivo {relative}.")
        else:
            return node_index
    raise ValueError(f"O caminho {relative} não foi encontrado no NUP.")


def inspect_nup(path: Path, layout: dict | None = None) -> dict:
    """Recognize the supported Pokopia update package inside an NUP container."""
    layout = layout or read_nup_layout(path)
    candidates = []
    observed_versions = []
    for package in layout["packages"]:
        if package["title_id"] != GAME_TITLE_ID or package["kind"] != NUP_KIND_UPDATE:
            continue
        indexes = {}
        try:
            for relative in ROMFS_FILES:
                indexes[relative] = nup_file_index(layout, package, relative)
        except ValueError:
            continue
        if package["version"] == NUP_UPDATE_VERSION:
            candidates.append((package, indexes))
        else:
            observed_versions.append(package["version"])
    if len(candidates) != 1:
        if not candidates and observed_versions:
            versions = ", ".join(str(value) for value in observed_versions)
            raise ValueError(
                "Encontrei os arquivos de Pokopia no NUP, mas a versão do update "
                f"não é a 2.0.1 (update 655360). Versões encontradas: {versions}."
            )
        if len(candidates) > 1:
            raise ValueError("O NUP contém mais de um update 2.0.1 compatível.")
        raise ValueError(
            "O NUP não contém o update de Pokémon Pokopia 2.0.1 "
            "(título 0400A3A01EE4C000, update 655360)."
        )
    package, indexes = candidates[0]
    return {
        "mode": "nup", "version": "2.0.1", "path": path.resolve(),
        "nup_package_index": package["index"], "nup_file_indexes": indexes,
    }


def inspect_nsp(path: Path) -> dict:
    """Recognize a valid PFS0 NSP; encrypted NCA payloads are not modified."""
    with path.open("rb") as source:
        header = source.read(16)
        if len(header) != 16:
            raise ValueError("O arquivo NSP está incompleto.")
        magic, count, string_size, _reserved = struct.unpack("<4sIII", header)
        if magic != b"PFS0" or count < 1 or count > 100000:
            raise ValueError("O arquivo não é um NSP PFS0 válido.")
        table_end = 16 + count * 24 + string_size
        if table_end > path.stat().st_size:
            raise ValueError("A tabela interna do NSP está incompleta.")
        source.seek(16 + count * 24)
        names = source.read(string_size)
        if len(names) != string_size:
            raise ValueError("A tabela de nomes do NSP está incompleta.")
        has_nca = False
        for index in range(count):
            source.seek(16 + index * 24)
            _offset, _size, name_offset, _reserved = struct.unpack(
                "<QQII", source.read(24)
            )
            if name_offset >= len(names):
                raise ValueError("O NSP contém um nome de arquivo inválido.")
            end = names.find(b"\0", name_offset)
            if end < 0:
                raise ValueError("O NSP contém um nome de arquivo incompleto.")
            if names[name_offset:end].lower().endswith(b".nca"):
                has_nca = True
        if not has_nca:
            raise ValueError("O NSP não contém arquivos NCA.")
    return {"mode": "nsp_mod", "version": "2.0.1", "path": path.resolve()}

IGNORED_DIRS = {
    ".git",
    ".cache",
    "cache",
    "shader",
    "shaders",
    "screenshots",
    "logs",
    "log",
    "backup",
    "backups",
}


def inspect_romfs(path: Path) -> dict | None:
    """Return a supported version when all expected RomFS filenames exist."""
    paths = {relative: path / Path(relative) for relative in ROMFS_FILES}
    if not all(candidate.is_file() for candidate in paths.values()):
        return None

    for version, signature in VERSIONS.items():
        return {
            "version": version,
            "update_id": signature["update_id"],
            "path": path.resolve(),
        }
    return None


def find_romfs(selected: Path) -> list[dict]:
    """Find supported romfs folders below a selected game/update directory."""
    selected = selected.resolve()
    found: dict[str, dict] = {}

    def add_candidate(folder: Path) -> None:
        result = inspect_romfs(folder)
        if result:
            found[str(result["path"]).casefold()] = result

    add_candidate(selected)
    max_depth = 6
    for current, dirs, _files in os.walk(selected, topdown=True, followlinks=False):
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(selected).parts)
        except ValueError:
            dirs[:] = []
            continue
        if depth >= max_depth:
            dirs[:] = []
            continue

        dirs[:] = [
            name
            for name in dirs
            if name.casefold() not in IGNORED_DIRS
            and not getattr(os.path, "isjunction", lambda _p: False)(
                str(current_path / name)
            )
        ]

        # Most emulator installs store the four files in an explicitly named romfs.
        if "romfs" in {name.casefold() for name in dirs}:
            romfs_name = next(name for name in dirs if name.casefold() == "romfs")
            add_candidate(current_path / romfs_name)
            dirs.remove(romfs_name)

    return sorted(found.values(), key=lambda item: (item["version"], str(item["path"]).casefold()))


def app_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def package_locations() -> tuple[Path, Path]:
    app_dir = app_directory()
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    )
    cache = local_app_data / "PokemonPokopiaPTBR" / "packages" / APP_VERSION
    return app_dir / PACKAGE_NAME, cache / PACKAGE_NAME


class FolderPackage:
    """Read translation members from version folders beside the installer."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _member_path(self, member: str) -> Path:
        parts = member.split("/")
        if not member or any(part in {"", ".", ".."} for part in parts):
            raise KeyError(member)
        candidate = self.root.joinpath(*parts)
        try:
            candidate.resolve().relative_to(self.root)
        except (OSError, ValueError):
            raise KeyError(member) from None
        if not candidate.is_file():
            raise KeyError(member)
        return candidate

    def getinfo(self, member: str) -> SimpleNamespace:
        return SimpleNamespace(file_size=self._member_path(member).stat().st_size)

    def open(self, member: str, mode: str = "r"):  # noqa: A002
        if mode not in {"r", "rb"}:
            raise ValueError("O pacote de tradução é somente leitura.")
        return self._member_path(member).open("rb")


def is_valid_bundled_package(root: Path) -> bool:
    """Accept a bundled payload when its expected files are present."""
    found_version = False
    for version in VERSIONS:
        romfs = root / version / "romfs"
        if not romfs.exists():
            continue
        found_version = True
        if not all((romfs / Path(relative)).is_file() for relative in ROMFS_FILES):
            return False
    return found_version


def is_valid_zip_package(path: Path) -> bool:
    """Verify that the ZIP contains each expected payload file exactly once."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            for version in VERSIONS:
                for relative in ROMFS_FILES:
                    member = f"{version}/romfs/{relative}"
                    if names.count(member) != 1:
                        return False
                    if archive.getinfo(member).file_size <= 0:
                        return False
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, RuntimeError, EOFError):
        return False
    return True


@contextmanager
def open_package(package: Path | FolderPackage):
    if isinstance(package, FolderPackage):
        yield package
    else:
        with zipfile.ZipFile(package, "r") as archive:
            yield archive


class Installer:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"Instalador Pokémon Pokopia PT-BR {APP_VERSION}")
        self.root.geometry("840x590")
        self.root.minsize(760, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.candidates: list[dict] = []
        self.checkboxes: list[tuple[dict, tk.BooleanVar]] = []

        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Instalar tradução PT-BR",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Escolha uma pasta do jogo/update ou um arquivo NSP/NUP. "
                "O instalador reconhece a tradução da versão 2.0.1."
            ),
            wraplength=770,
            justify="left",
        ).pack(anchor="w", pady=(8, 16))

        choose_row = ttk.Frame(frame)
        choose_row.pack(fill="x")
        self.choose_button = ttk.Button(
            choose_row, text="Selecionar pasta…", command=self.choose_folder
        )
        self.choose_button.pack(side="left")
        self.choose_package_button = ttk.Button(
            choose_row,
            text="Selecionar NSP/NUP…",
            command=self.choose_package_file,
        )
        self.choose_package_button.pack(side="left", padx=(8, 0))
        self.selected_path_label = ttk.Label(
            choose_row, text="Nenhuma pasta ou arquivo selecionado", wraplength=420
        )
        self.selected_path_label.pack(side="left", padx=(12, 0), fill="x", expand=True)

        self.status_label = ttk.Label(
            frame,
            text="Feche o jogo antes de instalar. O emulador pode permanecer aberto.",
            wraplength=710,
            justify="left",
        )
        self.status_label.pack(anchor="w", pady=(16, 8))

        self.list_frame = ttk.LabelFrame(
            frame, text="Versões encontradas", padding=(10, 8)
        )
        self.list_frame.pack(fill="both", expand=True, pady=(4, 12))
        self.empty_label = ttk.Label(
            self.list_frame,
            text="Selecione uma pasta, um arquivo NSP ou um arquivo NUP.",
            wraplength=660,
            justify="left",
        )
        self.empty_label.pack(anchor="w")

        self.progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 12))

        footer = ttk.Frame(frame)
        footer.pack(fill="x")
        ttk.Label(
            footer,
            text="Arquivos substituídos são guardados em AppData. NSP e NUP originais são preservados.",
            wraplength=490,
        ).pack(side="left", fill="x", expand=True)
        self.install_button = ttk.Button(
            footer,
            text="Aplicar tradução",
            command=self.install_selected,
            state="disabled",
        )
        self.install_button.pack(side="right")

        self.root.after(150, self.poll_events)

    def close(self) -> None:
        if self.busy:
            messagebox.showinfo(
                "Instalação em andamento",
                "Aguarde a instalação terminar antes de fechar esta janela.",
                parent=self.root,
            )
            return
        self.root.destroy()

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Selecione a pasta do jogo, do update ou de romfs",
            mustexist=True,
            parent=self.root,
        )
        if not folder:
            return

        self.selected_path_label.configure(text=folder)
        self.status_label.configure(text="Verificando a versão e os arquivos…")
        self.choose_button.configure(state="disabled")
        self.choose_package_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.clear_candidates()
        threading.Thread(
            target=self.detect_worker, args=(Path(folder),), daemon=True
        ).start()

    def choose_package_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecione o NSP ou NUP de Pokémon Pokopia",
            filetypes=[
                ("Pacotes NSP/NUP", "*.nsp *.nup"),
                ("NSP", "*.nsp"),
                ("NUP", "*.nup"),
                ("Todos os arquivos", "*.*"),
            ],
            parent=self.root,
        )
        if not filename:
            return

        self.selected_path_label.configure(text=filename)
        self.status_label.configure(text="Verificando o arquivo selecionado…")
        self.choose_button.configure(state="disabled")
        self.choose_package_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.clear_candidates()
        threading.Thread(
            target=self.detect_worker, args=(Path(filename),), daemon=True
        ).start()

    def detect_worker(self, folder: Path) -> None:
        try:
            if folder.is_file():
                suffix = folder.suffix.casefold()
                if suffix == ".nup":
                    results = [inspect_nup(folder)]
                elif suffix == ".nsp":
                    results = [inspect_nsp(folder)]
                else:
                    raise ValueError("Selecione uma pasta, um arquivo .NSP ou um .NUP.")
            else:
                results = find_romfs(folder)
            self.events.put(("detected", results))
        except Exception as exc:
            self.events.put(("detect_error", str(exc)))

    def clear_candidates(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.checkboxes.clear()

    def display_candidates(self, results: list[dict]) -> None:
        self.candidates = results
        self.clear_candidates()
        self.choose_button.configure(state="normal")
        self.choose_package_button.configure(state="normal")

        if not results:
            self.status_label.configure(
                text=(
                    "Não encontrei um update compatível. Selecione a pasta romfs "
                    "ou a pasta do update que contenha LD_C0_R.BIN, LI_C0_R.IDX "
                    "e os arquivos motor_asset_re, ou escolha um arquivo .NSP/.NUP."
                )
            )
            ttk.Label(
                self.list_frame,
                text="Nenhuma instalação compatível com a tradução 2.0.1 foi reconhecida.",
                wraplength=660,
                justify="left",
            ).pack(anchor="w")
            return

        if len(results) == 1:
            candidate = results[0]
            if candidate.get("mode") == "nsp_mod":
                status = (
                    "NSP reconhecido. O instalador criará um mod LayeredFS para "
                    "Pokopia 2.0.1; a versão interna do NSP criptografado não pode "
                    "ser lida aqui."
                )
            elif candidate.get("mode") == "nup":
                status = "Pokémon Pokopia 2.0.1 reconhecido dentro do NUP."
            else:
                status = f"Versão identificada: {candidate['version']}."
            self.status_label.configure(text=status)
        else:
            self.status_label.configure(
                text=(
                    f"Encontrei {len(results)} pastas de update compatíveis. "
                    "Marque a(s) versão(ões) em que deseja instalar."
                )
            )

        for index, candidate in enumerate(results):
            version = candidate["version"]
            path = candidate["path"]
            var = tk.BooleanVar(value=(len(results) == 1))
            row = ttk.Frame(self.list_frame)
            row.pack(fill="x", pady=3)
            if candidate.get("mode") == "nup":
                description = f"Pokémon Pokopia {version} — arquivo NUP (update 655360)"
            elif candidate.get("mode") == "nsp_mod":
                description = f"Pokémon Pokopia {version} — NSP; instalação como mod LayeredFS"
            else:
                description = (
                    f"Pokémon Pokopia {version} "
                    f"(update {candidate['update_id']})"
                )
            check = ttk.Checkbutton(
                row,
                text=description,
                variable=var,
                command=self.update_install_button,
            )
            check.pack(anchor="w")
            ttk.Label(
                row, text=str(path), wraplength=650, justify="left"
            ).pack(anchor="w", padx=(24, 0))
            self.checkboxes.append((candidate, var))

        self.update_install_button()

    def update_install_button(self) -> None:
        selected = any(var.get() for _candidate, var in self.checkboxes)
        self.install_button.configure(state="normal" if selected and not self.busy else "disabled")

    def install_selected(self) -> None:
        selected = [
            candidate
            for candidate, var in self.checkboxes
            if var.get()
        ]
        if not selected or self.busy:
            return

        for item in selected:
            if item.get("mode") == "nup":
                source_path = Path(item["path"])
                base_name = f"{source_path.stem}-PTBR{source_path.suffix}"
                default_path = source_path.with_name(base_name)
                suffix = 2
                while default_path.exists():
                    default_path = source_path.with_name(
                        f"{source_path.stem}-PTBR-{suffix}{source_path.suffix}"
                    )
                    suffix += 1
                output = filedialog.asksaveasfilename(
                    title="Salvar cópia NUP traduzida",
                    initialdir=str(source_path.parent),
                    initialfile=default_path.name,
                    defaultextension=".nup",
                    filetypes=[("Arquivo NUP", "*.nup")],
                    parent=self.root,
                )
                if not output:
                    return
                output_path = Path(output).resolve()
                if output_path == source_path.resolve():
                    messagebox.showerror(
                        "Destino inválido",
                        "Escolha um nome diferente para manter o NUP original intacto.",
                        parent=self.root,
                    )
                    return
                if output_path.exists():
                    messagebox.showerror(
                        "Arquivo já existe",
                        "Escolha um arquivo de saída que ainda não exista. O instalador "
                        "preserva o NUP original e não sobrescreve outro arquivo.",
                        parent=self.root,
                    )
                    return
                item["output_path"] = output_path

            elif item.get("mode") == "nsp_mod":
                if not messagebox.askyesno(
                    "Instalação de NSP como mod",
                    "O NSP contém arquivos NCA criptografados e permanecerá intacto. "
                    "A tradução será instalada como mod LayeredFS do Eglantine para "
                    "Pokémon Pokopia 2.0.1.\n\n"
                    "Continuar e escolher a pasta user do Eglantine?",
                    parent=self.root,
                ):
                    return
                user_folder = filedialog.askdirectory(
                    title="Selecione a pasta user do Eglantine (ou a pasta load)",
                    mustexist=True,
                    parent=self.root,
                )
                if not user_folder:
                    return
                selected_root = Path(user_folder).resolve()
                if selected_root.name.casefold() == "load":
                    load_root = selected_root
                elif selected_root.name.casefold() == "user":
                    load_root = selected_root / "load"
                elif (selected_root / "user").is_dir():
                    load_root = selected_root / "user" / "load"
                else:
                    load_root = selected_root / "load"
                item["romfs_path"] = load_root / GAME_TITLE_ID_HEX / "romfs"

        summary = "\n".join(
            f"• {item['version']}: {item.get('output_path', item.get('romfs_path', item['path']))}"
            for item in selected
        )
        if any(item.get("mode") == "nup" for item in selected):
            intro = (
                "Vou criar uma cópia NUP traduzida e manter o arquivo original intacto:\n\n"
            )
        elif any(item.get("mode") == "nsp_mod" for item in selected):
            intro = (
                "Vou instalar os arquivos como mod LayeredFS no perfil do Eglantine. "
                "O NSP original não será alterado; os arquivos substituídos no mod "
                "serão guardados em AppData.\n\n"
            )
        else:
            intro = (
                "Vou aplicar a tradução nas pastas abaixo e criar backups dos arquivos atuais:\n\n"
            )
        if not messagebox.askyesno(
            "Confirmar instalação",
            intro + summary
            + "\n\nContinuar?",
            parent=self.root,
        ):
            return

        self.busy = True
        self.choose_button.configure(state="disabled")
        self.choose_package_button.configure(state="disabled")
        self.install_button.configure(state="disabled")
        self.progress.configure(value=0)
        self.status_label.configure(text="Preparando o pacote de tradução…")
        threading.Thread(
            target=self.install_worker, args=(selected,), daemon=True
        ).start()

    def install_worker(self, targets: list[dict]) -> None:
        outcomes: list[dict] = []
        try:
            package = self.ensure_package()
            with open_package(package) as archive:
                for target in targets:
                    try:
                        output = None
                        if target.get("mode") == "nup":
                            output = self.apply_nup_patch(archive, target)
                            backup = None
                        elif target.get("mode") == "nsp_mod":
                            backup = self.apply_layeredfs(archive, target)
                        else:
                            backup = self.apply_patch(archive, target)
                        outcomes.append(
                            {
                                "version": target["version"],
                                "path": str(target["path"]),
                                "mode": target.get("mode", "folder"),
                                "romfs_path": str(target.get("romfs_path", "")),
                                "output": str(output) if output else None,
                                "backup": str(backup) if backup else None,
                                "already_installed": backup is None and output is None,
                                "error": None,
                            }
                        )
                    except Exception as exc:
                        outcomes.append(
                            {
                                "version": target["version"],
                                "path": str(target["path"]),
                                "mode": target.get("mode", "folder"),
                                "romfs_path": str(target.get("romfs_path", "")),
                                "output": None,
                                "backup": None,
                                "already_installed": False,
                                "error": str(exc),
                            }
                        )
            self.events.put(("complete", outcomes))
        except Exception as exc:
            self.events.put(("fatal_error", str(exc)))

    def ensure_package(self) -> Path | FolderPackage:
        bundled_root = app_directory()
        if is_valid_bundled_package(bundled_root):
            self.events.put(
                ("status", "Usando os arquivos de tradução incluídos no ZIP…")
            )
            return FolderPackage(bundled_root)

        adjacent, cached = package_locations()
        for candidate in (adjacent, cached):
            if candidate.is_file():
                self.events.put(("status", "Verificando o pacote de tradução…"))
                if is_valid_zip_package(candidate):
                    return candidate
                if candidate == cached:
                    try:
                        candidate.unlink()
                    except OSError:
                        pass

        cached.parent.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(cached.suffix + ".part")
        request = urllib.request.Request(
            PACKAGE_URL,
            headers={"User-Agent": f"Pokopia-PTBR-Installer/{APP_VERSION}"},
        )
        try:
            self.events.put(("status", "Baixando o pacote de tradução…"))
            with urllib.request.urlopen(request, timeout=60) as response:
                total = int(response.headers.get("Content-Length", "0") or "0")
                downloaded = 0
                with partial.open("wb") as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        downloaded += len(block)
                        percent = int(downloaded * 100 / total) if total else 0
                        self.events.put(
                            ("progress", percent, downloaded, total)
                        )
            if not is_valid_zip_package(partial):
                raise ValueError(
                    "O pacote baixado não contém todos os arquivos esperados."
                )
            os.replace(partial, cached)
            self.events.put(("progress", 100, cached.stat().st_size, cached.stat().st_size))
            return cached
        except Exception:
            try:
                partial.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def apply_nup_patch(self, archive: zipfile.ZipFile, target: dict) -> Path | None:
        """Create a translated NUP copy, preserving every unrelated extent and package."""
        source_path = Path(target["path"])
        output_path = Path(target["output_path"])
        if source_path.resolve() == output_path.resolve():
            raise ValueError("O NUP traduzido precisa ser salvo em outro arquivo.")
        if output_path.exists():
            raise FileExistsError(f"O arquivo de saída já existe: {output_path}")

        layout = read_nup_layout(source_path)
        self.events.put(("status", "NUP reconhecido. Preparando os quatro arquivos traduzidos…"))
        current_target = inspect_nup(source_path, layout)
        if (current_target["nup_package_index"] != target["nup_package_index"]
                or current_target["nup_file_indexes"] != target["nup_file_indexes"]):
            raise ValueError("O NUP mudou desde a verificação. Selecione-o novamente.")

        version = target["version"]
        member_names = {
            relative: f"{version}/romfs/{relative}" for relative in ROMFS_FILES
        }
        stage = Path(tempfile.mkdtemp(prefix="pokopia-nup-stage-"))
        temp_output: Path | None = None
        try:
            staged_files: dict[str, dict] = {}
            for relative, member in member_names.items():
                try:
                    info = archive.getinfo(member)
                except KeyError as exc:
                    raise ValueError(f"O pacote não contém {member}.") from exc
                if info.file_size <= 0:
                    raise ValueError(f"O arquivo do pacote está vazio: {member}")
                staged = stage / Path(relative)
                staged.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                total = 0
                with archive.open(member, "r") as source, staged.open("wb") as output:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        digest.update(block)
                        total += len(block)
                if total != info.file_size:
                    raise IOError(f"Extração incompleta do arquivo {member}.")
                staged_files[relative] = {
                    "path": staged, "size": total, "sha256": digest.digest(),
                    "file_index": target["nup_file_indexes"][relative],
                }

            if all(
                layout["files"][entry["file_index"]]["sha256"] == entry["sha256"]
                for entry in staged_files.values()
            ):
                return None

            source_size = layout["file_size"]
            metadata_start = min(
                (package["meta_offset"] for package in layout["packages"]
                 if package["meta_size"]),
                default=source_size,
            )
            if metadata_start < layout["blob_offset"] or metadata_start > source_size:
                raise ValueError("A área de metadados do NUP está fora dos limites.")
            if any(
                file["size"] and file["extent_offset"] + file["extent_size"] > metadata_start
                for file in layout["files"]
            ):
                raise ValueError(
                    "O layout deste NUP não permite inserir a tradução sem mover "
                    "dados de outros arquivos."
                )

            cursor = metadata_start
            extent_offsets: dict[str, int] = {}
            for relative in ROMFS_FILES:
                aligned = _align(cursor, NUP_EXTENT_ALIGNMENT)
                extent_offsets[relative] = aligned
                cursor = aligned + staged_files[relative]["size"]
            shift = cursor - metadata_start
            new_file_size = source_size + shift

            toc = bytearray(layout["toc"])
            for relative, entry in staged_files.items():
                record_offset = layout["files"][entry["file_index"]]["offset"]
                name_offset, name_length = struct.unpack_from("<II", toc, record_offset)
                NUP_FILE.pack_into(
                    toc, record_offset, name_offset, name_length,
                    entry["size"], extent_offsets[relative], entry["size"],
                    entry["sha256"], 0, 0, 0,
                )
            for package in layout["packages"]:
                if package["meta_size"]:
                    struct.pack_into(
                        "<Q", toc, package["offset"] + 32,
                        package["meta_offset"] + shift,
                    )

            header = bytearray(layout["header"])
            struct.pack_into("<32s", header, 0x18, hashlib.sha256(toc).digest())
            struct.pack_into("<Q", header, 0x40, new_file_size)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=".pokopia-ptbr-", suffix=".nup.tmp", dir=output_path.parent
            )
            os.close(fd)
            temp_output = Path(temp_name)

            def copy_range(source, output, start: int, length: int) -> None:
                if length < 0:
                    raise ValueError("Um segmento do NUP tem tamanho inválido.")
                source.seek(start)
                remaining = length
                while remaining:
                    block = source.read(min(4 * 1024 * 1024, remaining))
                    if not block:
                        raise IOError("Leitura incompleta do NUP original.")
                    output.write(block)
                    remaining -= len(block)

            with source_path.open("rb") as source, temp_output.open("wb") as output:
                self.events.put((
                    "status",
                    "Copiando os dados do NUP sem descompactar o jogo. "
                    "A cópia de saída pode ter vários gigabytes…",
                ))
                output.write(header)
                copy_range(source, output, NUP_HEADER.size,
                           layout["toc_offset"] - NUP_HEADER.size)
                output.write(toc)
                data_start = layout["toc_offset"] + layout["toc_size"]
                copy_range(source, output, data_start, metadata_start - data_start)

                written = metadata_start
                for relative in ROMFS_FILES:
                    extent_offset = extent_offsets[relative]
                    if extent_offset > written:
                        output.write(b"\0" * (extent_offset - written))
                    with staged_files[relative]["path"].open("rb") as staged:
                        shutil.copyfileobj(staged, output, 1024 * 1024)
                    written = extent_offset + staged_files[relative]["size"]
                copy_range(source, output, metadata_start, source_size - metadata_start)
                output.flush()
                os.fsync(output.fileno())

            verified = read_nup_layout(temp_output)
            verified_target = inspect_nup(temp_output, verified)
            for relative, entry in staged_files.items():
                written_file = verified["files"][verified_target["nup_file_indexes"][relative]]
                if (written_file["size"] != entry["size"]
                        or written_file["sha256"] != entry["sha256"]):
                    raise IOError(f"A validação da saída NUP falhou para {relative}.")

            if output_path.exists():
                raise FileExistsError(f"O arquivo de saída já existe: {output_path}")
            os.rename(temp_output, output_path)
            temp_output = None
            return output_path
        finally:
            if temp_output is not None:
                try:
                    temp_output.unlink(missing_ok=True)
                except OSError:
                    pass
            shutil.rmtree(stage, ignore_errors=True)

    def apply_layeredfs(self, archive: zipfile.ZipFile, target: dict) -> Path | None:
        """Install translation files under user/load/<title-id>/romfs for an NSP."""
        version = target["version"]
        romfs = Path(target["romfs_path"])
        member_names = {
            relative: f"{version}/romfs/{relative}" for relative in ROMFS_FILES
        }
        stage_parent = romfs.parent
        stage_parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".pokopia-ptbr-stage-", dir=stage_parent))
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target_key = hashlib.sha256(
            str(romfs.resolve()).casefold().encode("utf-8")
        ).hexdigest()[:8]
        backup = (
            local_app_data
            / "PokemonPokopiaPTBR"
            / "backups"
            / stamp
            / f"2.0.1-layeredfs-{target_key}"
        )
        replaced: list[str] = []
        try:
            staged_files: dict[str, dict] = {}
            for relative, member in member_names.items():
                try:
                    info = archive.getinfo(member)
                except KeyError as exc:
                    raise ValueError(f"O pacote não contém {member}.") from exc
                if info.file_size <= 0:
                    raise ValueError(f"O arquivo do pacote está vazio: {member}")
                staged = stage / Path(relative)
                staged.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                total = 0
                with archive.open(member, "r") as source, staged.open("wb") as output:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        digest.update(block)
                        total += len(block)
                if total != info.file_size:
                    raise IOError(f"Extração incompleta do arquivo {member}.")
                staged_files[relative] = {"path": staged, "sha256": digest.digest()}

            if all(
                (romfs / Path(relative)).is_file()
                and self._file_sha256(romfs / Path(relative)) == entry["sha256"]
                for relative, entry in staged_files.items()
            ):
                return None

            backup.mkdir(parents=True, exist_ok=False)
            backed_up = []
            for relative in ROMFS_FILES:
                current = romfs / Path(relative)
                if not current.is_file():
                    continue
                destination = backup / Path(relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, destination)
                backed_up.append(relative)

            manifest = {
                "installer_version": APP_VERSION,
                "game_version": version,
                "title_id": GAME_TITLE_ID_HEX,
                "source_nsp": str(target["path"]),
                "romfs_path": str(romfs),
                "created_at": datetime.now().astimezone().isoformat(),
                "files": list(ROMFS_FILES),
                "backed_up_files": backed_up,
            }
            (backup / "backup-manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            try:
                for relative in ROMFS_FILES:
                    destination = romfs / Path(relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(staged_files[relative]["path"], destination)
                    replaced.append(relative)
            except Exception:
                for relative in replaced:
                    saved = backup / Path(relative)
                    destination = romfs / Path(relative)
                    if saved.is_file():
                        shutil.copy2(saved, destination)
                    else:
                        destination.unlink(missing_ok=True)
                raise
            return backup
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    @staticmethod
    def _file_sha256(path: Path) -> bytes:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    return digest.digest()
                digest.update(block)

    def apply_patch(self, archive: zipfile.ZipFile, target: dict) -> Path | None:
        version = target["version"]
        romfs = Path(target["path"])
        signature = VERSIONS[version]
        member_names = {
            relative: f"{version}/romfs/{relative}" for relative in ROMFS_FILES
        }

        for relative, member in member_names.items():
            try:
                info = archive.getinfo(member)
            except KeyError as exc:
                raise ValueError(f"O pacote não contém {member}.") from exc
            if info.file_size <= 0:
                raise ValueError(f"O arquivo do pacote está vazio: {member}")

        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target_key = hashlib.sha256(
            str(romfs.resolve()).casefold().encode("utf-8")
        ).hexdigest()[:8]
        backup = (
            local_app_data
            / "PokemonPokopiaPTBR"
            / "backups"
            / stamp
            / f"{version}-{target_key}"
        )
        backup.mkdir(parents=True, exist_ok=False)

        # Preserve the current game files before changing any of them.
        for relative in ROMFS_FILES:
            source = romfs / Path(relative)
            if not source.is_file():
                raise FileNotFoundError(f"Arquivo ausente na pasta do jogo: {source}")
            destination = backup / Path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        manifest = {
            "installer_version": APP_VERSION,
            "game_version": version,
            "update_id": signature["update_id"],
            "romfs_path": str(romfs),
            "created_at": datetime.now().astimezone().isoformat(),
            "files": list(ROMFS_FILES),
        }
        (backup / "backup-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        stage = Path(tempfile.mkdtemp(prefix=".pokopia-ptbr-stage-", dir=romfs))
        replaced: list[str] = []
        try:
            for relative, member in member_names.items():
                staged = stage / Path(relative)
                staged.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, staged.open("wb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                if staged.stat().st_size != archive.getinfo(member).file_size:
                    raise IOError(f"Extração incompleta do arquivo {member}.")

            for relative in ROMFS_FILES:
                os.replace(stage / Path(relative), romfs / Path(relative))
                replaced.append(relative)
        except Exception:
            # Restore every file if a replacement was interrupted.
            for relative in replaced:
                saved = backup / Path(relative)
                if saved.is_file():
                    shutil.copy2(saved, romfs / Path(relative))
            raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        return backup

    def poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "detected":
                    self.display_candidates(event[1])
                elif kind == "detect_error":
                    self.choose_button.configure(state="normal")
                    self.choose_package_button.configure(state="normal")
                    self.status_label.configure(text="Falha ao verificar a pasta.")
                    messagebox.showerror(
                        "Erro na verificação", event[1], parent=self.root
                    )
                elif kind == "status":
                    self.status_label.configure(text=event[1])
                elif kind == "progress":
                    _kind, percent, downloaded, total = event
                    self.progress.configure(value=percent)
                    if total:
                        self.status_label.configure(
                            text=(
                                "Baixando o pacote: "
                                f"{downloaded // (1024 * 1024)} / "
                                f"{total // (1024 * 1024)} MB"
                            )
                        )
                elif kind == "complete":
                    self.finish_install(event[1])
                elif kind == "fatal_error":
                    self.finish_error(event[1])
        except queue.Empty:
            pass
        self.root.after(150, self.poll_events)

    def finish_install(self, outcomes: list[dict]) -> None:
        self.busy = False
        self.choose_button.configure(state="normal")
        self.choose_package_button.configure(state="normal")
        self.update_install_button()
        self.progress.configure(value=100)

        lines = []
        errors = []
        for result in outcomes:
            if result["error"]:
                errors.append(f"{result['version']} — {result['path']}\n{result['error']}")
            elif result["already_installed"]:
                if result["mode"] == "nup":
                    lines.append("O NUP selecionado já contém esses arquivos traduzidos.")
                elif result["mode"] == "nsp_mod":
                    lines.append("O mod LayeredFS já contém a tradução atual.")
                else:
                    lines.append(f"{result['version']}: a tradução já estava instalada.")
            elif result["output"]:
                lines.append(
                    "Cópia NUP traduzida criada:\n"
                    f"{result['output']}\nO NUP original foi mantido intacto."
                )
            elif result["mode"] == "nsp_mod":
                lines.append(
                    "Mod LayeredFS instalado em:\n"
                    f"{result['romfs_path']}\n"
                    "O NSP original foi mantido intacto.\n"
                    f"Backup dos arquivos de mod anteriores: {result['backup']}"
                )
            else:
                lines.append(
                    f"{result['version']}: instalado.\nBackup: {result['backup']}"
                )

        if errors:
            self.status_label.configure(text="A instalação terminou com erro em uma ou mais pastas.")
            messagebox.showerror(
                "Instalação incompleta",
                "\n\n".join(lines + errors),
                parent=self.root,
            )
        else:
            self.status_label.configure(text="Tradução aplicada com sucesso.")
            messagebox.showinfo(
                "Concluído",
                "\n\n".join(lines),
                parent=self.root,
            )

    def finish_error(self, error: str) -> None:
        self.busy = False
        self.choose_button.configure(state="normal")
        self.choose_package_button.configure(state="normal")
        self.update_install_button()
        self.progress.configure(value=0)
        self.status_label.configure(text="Não foi possível concluir a instalação.")
        messagebox.showerror(
            "Erro ao instalar",
            "O instalador não conseguiu preparar ou aplicar o pacote.\n\n"
            + error
            + "\n\nConfira sua conexão e tente novamente.",
            parent=self.root,
        )

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    Installer().run()
