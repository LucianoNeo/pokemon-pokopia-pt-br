from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
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


APP_VERSION = "2.2.1"
PACKAGE_NAME = "Pokemon-Pokopia-PT-BR-v2.1.0.zip"
PACKAGE_URL = (
    "https://github.com/LucianoNeo/pokemon-pokopia-pt-br/releases/download/"
    "v2.1.0/Pokemon-Pokopia-PT-BR-v2.1.0.zip"
)
PACKAGE_SHA256 = "eead278132fabead5e5cb79b93676938c58c0622a3b41e648f56b995a42a857c"

ROMFS_FILES = (
    "LD_C0_R.BIN",
    "LI_C0_R.IDX",
    "motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb",
    "motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata",
)

# The index and asset sizes distinguish the two supported game updates.
VERSIONS = {
    "1.0.4": {
        "update_id": "327680",
        "idx_size": 377056,
        "rdb_size": 4846712,
        "fdata_size": 19537088,
        "hashes": {
            "LD_C0_R.BIN": "41a15ee18a4571a226dfa52823fa43b845158821eda33074973609b662862c32",
            "LI_C0_R.IDX": "640d956722cbdf79a113dbc98dde863549bbf87020f9bdc4deacffe703a4edbd",
            "motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb": "c44a37e44b1e17338c2c375b6ad9c9604bdafcc7d427dccaede642bf196fe11d",
            "motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata": "07edabc2d403d9508d82228c687dd7e54424ab20bddb287276ad027f748c7ba7",
        },
    },
    "2.0.1": {
        "update_id": "655360",
        "idx_size": 393536,
        "rdb_size": 5752340,
        "fdata_size": 21896960,
        # Original 2.0.1/2.0.1a RomFS files. The previous installer compared
        # source files against translated output sizes, so clean installations
        # were rejected before the patch could be applied.
        "source_sizes": {
            "LD_C0_R.BIN": 247317504,
            "LI_C0_R.IDX": 393536,
            "motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb": 5752340,
            "motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata": 264309,
        },
        "source_hashes": {
            "LD_C0_R.BIN": "2ea76fd78d5d2c0111fc2e3d8258ed35faaad6a52420d7fdee7c8a2ed2122433",
            "LI_C0_R.IDX": "86fb3fae4e3092594e45c350f7f12e4cbe4a53b513f07c1f38498f6ec988c0b1",
            "motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb": "47f715d98cbe8718ce0c5e51dd4666c6587796a51f72b904a76bde8d227be786",
            "motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata": "61ec376dc272d65c21dc93d8e91502b796d81e6ddcaae564670340485da197da",
        },
        "hashes": {
            "LD_C0_R.BIN": "7982642fe324a939755abe0f095846dea0ac366f8c9a1c799c61c53f628ed249",
            "LI_C0_R.IDX": "52c517e6d52807ae853542eb1217c733e62f25f01316713657a53277033b1335",
            "motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb": "bb102f85a7293760db8c9d6b1ac1546e64e7b1da2a3a76cbbb1b464bb08ee609",
            "motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata": "914d1615fc3b4a6307db05678842cac739ac55d088ad4d4aa26444b448f0d891",
        },
    },
}

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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_romfs(path: Path) -> dict | None:
    """Return a supported version when its source or translated files match."""
    paths = {relative: path / Path(relative) for relative in ROMFS_FILES}
    if not all(candidate.is_file() for candidate in paths.values()):
        return None

    try:
        sizes = {
            relative: candidate.stat().st_size
            for relative, candidate in paths.items()
        }
    except OSError:
        return None

    for version, signature in VERSIONS.items():
        source_sizes = signature.get("source_sizes")
        source_hashes = signature.get("source_hashes")
        if source_sizes and source_hashes and all(
            sizes.get(relative) == expected_size
            for relative, expected_size in source_sizes.items()
        ):
            try:
                if all(
                    sha256_file(paths[relative]) == expected_hash
                    for relative, expected_hash in source_hashes.items()
                ):
                    return {
                        "version": version,
                        "update_id": signature["update_id"],
                        "path": path.resolve(),
                    }
            except OSError:
                return None

        # The bundled hashes and sizes describe the translated output. Keep the
        # legacy 1.0.4 size check because its original source fingerprint was
        # not recorded; 2.0.1 must match exact source or output hashes.
        output_sizes_match = (
            sizes.get("LI_C0_R.IDX") == signature["idx_size"]
            and sizes.get("motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb")
            == signature["rdb_size"]
            and sizes.get("motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata")
            == signature["fdata_size"]
        )
        if output_sizes_match:
            try:
                output_hashes_match = all(
                    sha256_file(paths[relative]) == expected_hash
                    for relative, expected_hash in signature["hashes"].items()
                )
            except OSError:
                return None
            if output_hashes_match or version == "1.0.4":
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
    """Accept adjacent version folders only when every included file matches."""
    found_version = False
    for version, signature in VERSIONS.items():
        romfs = root / version / "romfs"
        if not romfs.exists():
            continue
        found_version = True
        try:
            for relative, expected_hash in signature["hashes"].items():
                candidate = romfs / Path(relative)
                if not candidate.is_file() or sha256_file(candidate) != expected_hash:
                    return False
        except OSError:
            return False
    return found_version


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
        self.root.geometry("780x560")
        self.root.minsize(700, 500)
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
                "Escolha a pasta do jogo, do update ou a pasta romfs. "
                "O instalador reconhece as versões 1.0.4 e 2.0.1."
            ),
            wraplength=710,
            justify="left",
        ).pack(anchor="w", pady=(8, 16))

        choose_row = ttk.Frame(frame)
        choose_row.pack(fill="x")
        self.choose_button = ttk.Button(
            choose_row, text="Selecionar pasta…", command=self.choose_folder
        )
        self.choose_button.pack(side="left")
        self.selected_path_label = ttk.Label(
            choose_row, text="Nenhuma pasta selecionada", wraplength=570
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
            text="Selecione uma pasta para procurar os arquivos do update.",
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
            text="Antes de substituir, o instalador guarda os arquivos atuais em AppData.",
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
        self.install_button.configure(state="disabled")
        self.clear_candidates()
        threading.Thread(
            target=self.detect_worker, args=(Path(folder),), daemon=True
        ).start()

    def detect_worker(self, folder: Path) -> None:
        try:
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

        if not results:
            self.status_label.configure(
                text=(
                    "Não encontrei um update compatível. Selecione a pasta romfs "
                    "ou a pasta do update que contenha LD_C0_R.BIN, LI_C0_R.IDX "
                    "e os arquivos motor_asset_re."
                )
            )
            ttk.Label(
                self.list_frame,
                text="Nenhuma instalação 1.0.4 ou 2.0.1 reconhecida.",
                wraplength=660,
                justify="left",
            ).pack(anchor="w")
            return

        if len(results) == 1:
            self.status_label.configure(
                text=f"Versão identificada: {results[0]['version']}."
            )
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
            check = ttk.Checkbutton(
                row,
                text=f"Pokémon Pokopia {version} (update {candidate['update_id']})",
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

        summary = "\n".join(
            f"• {item['version']}: {item['path']}" for item in selected
        )
        if not messagebox.askyesno(
            "Confirmar instalação",
            "Vou aplicar a tradução nas pastas abaixo e criar backups dos arquivos atuais:\n\n"
            + summary
            + "\n\nContinuar?",
            parent=self.root,
        ):
            return

        self.busy = True
        self.choose_button.configure(state="disabled")
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
                        backup = self.apply_patch(archive, target)
                        outcomes.append(
                            {
                                "version": target["version"],
                                "path": str(target["path"]),
                                "backup": str(backup) if backup else None,
                                "already_installed": backup is None,
                                "error": None,
                            }
                        )
                    except Exception as exc:
                        outcomes.append(
                            {
                                "version": target["version"],
                                "path": str(target["path"]),
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
                if sha256_file(candidate) == PACKAGE_SHA256:
                    return candidate
                if candidate == cached:
                    try:
                        candidate.unlink()
                    except OSError:
                        pass

        cached.parent.mkdir(parents=True, exist_ok=True)
        partial = cached.with_suffix(cached.suffix + ".part")
        digest = hashlib.sha256()
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
                        digest.update(block)
                        downloaded += len(block)
                        percent = int(downloaded * 100 / total) if total else 0
                        self.events.put(
                            ("progress", percent, downloaded, total)
                        )
            if digest.hexdigest() != PACKAGE_SHA256:
                raise ValueError(
                    "O SHA-256 do pacote baixado não corresponde à release oficial."
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

        if self.is_already_installed(romfs, signature["hashes"], archive, member_names):
            self.events.put(
                ("status", f"A versão {version} já está traduzida; sem alterações.")
            )
            return None

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

    @staticmethod
    def is_already_installed(
        romfs: Path, expected_hashes: dict, archive: zipfile.ZipFile, members: dict
    ) -> bool:
        for relative in ROMFS_FILES:
            target = romfs / Path(relative)
            if not target.is_file():
                return False
            if target.stat().st_size != archive.getinfo(members[relative]).file_size:
                return False
        return all(
            sha256_file(romfs / Path(relative)) == expected_hashes[relative]
            for relative in ROMFS_FILES
        )

    def poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "detected":
                    self.display_candidates(event[1])
                elif kind == "detect_error":
                    self.choose_button.configure(state="normal")
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
        self.update_install_button()
        self.progress.configure(value=100)

        lines = []
        errors = []
        for result in outcomes:
            if result["error"]:
                errors.append(f"{result['version']} — {result['path']}\n{result['error']}")
            elif result["already_installed"]:
                lines.append(f"{result['version']}: a tradução já estava instalada.")
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
