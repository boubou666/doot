"""Packs de contenu doot, archives ZIP declaratives et sures."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path


VERSION = 2
FOLDERS = {"sound", "image", "melodies", "events"}
MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024


def safe_name(value: str) -> str:
    name = re.sub(r"[^\w-]+", "-", str(value).strip(), flags=re.UNICODE).strip("-_")
    if not name:
        raise ValueError("donne un nom au pack")
    return name[:64]


def export(root: Path, destination: Path, name: str, *, author: str = "",
           description: str = "", pack_version: str = "1.0") -> Path:
    root, destination = Path(root), Path(destination)
    if destination.suffix.casefold() != ".zip":
        destination = destination / f"{safe_name(name)}.dootpack.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    files = []
    for folder in sorted(FOLDERS):
        source = root / folder
        if not source.is_dir():
            continue
        for path in sorted(source.iterdir()):
            if path.is_file() and path.stat().st_size <= MAX_FILE:
                files.append((path, f"{folder}/{path.name}"))
    profile_path = root / "profiles.json"
    if profile_path.is_file() and profile_path.stat().st_size <= MAX_FILE:
        files.append((profile_path, "config/profiles.json"))
    manifest = {
        "format": "doot-pack", "version": VERSION, "name": str(name).strip(),
        "author": str(author).strip()[:80], "description": str(description).strip()[:500],
        "pack_version": str(pack_version).strip()[:24] or "1.0",
        "files": {archive_name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path, archive_name in files},
    }
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path, archive_name in files:
                archive.write(path, archive_name)
        os.replace(temporary, destination)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return destination


def _destination(directory: Path, name: str) -> Path:
    candidate = directory / name
    stem, suffix, number = candidate.stem, candidate.suffix, 2
    while candidate.exists():
        candidate = directory / f"{stem}-{number}{suffix}"
        number += 1
    return candidate


def inspect(archive_path: Path, verify: bool = True) -> dict:
    """Lit les metadonnees et, en v2, verifie chaque empreinte SHA-256."""

    with zipfile.ZipFile(Path(archive_path)) as archive:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except Exception as exc:
            raise ValueError("manifest.json absent ou illisible") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != "doot-pack":
            raise ValueError("ce fichier n'est pas un pack doot")
        version = manifest.get("version", 1)
        if isinstance(version, bool) or not isinstance(version, int) or version not in (1, VERSION):
            raise ValueError("version de pack non prise en charge")
        digests = manifest.get("files", {})
        if verify and version >= 2:
            if not isinstance(digests, dict):
                raise ValueError("liste d'empreintes absente")
            for name, expected in digests.items():
                try:
                    actual = hashlib.sha256(archive.read(name)).hexdigest()
                except KeyError as exc:
                    raise ValueError(f"fichier annonce absent : {name}") from exc
                if actual != expected:
                    raise ValueError(f"empreinte invalide : {name}")
        return {
            "name": str(manifest.get("name", "pack")),
            "author": str(manifest.get("author", "")),
            "description": str(manifest.get("description", "")),
            "pack_version": str(manifest.get("pack_version", "1.0")),
            "format_version": version,
            "files": len(digests) if isinstance(digests, dict) else 0,
            "verified": bool(version >= 2 and verify),
        }


def library(directory: Path) -> list[tuple[Path, dict]]:
    result = []
    directory = Path(directory)
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.zip")):
        try:
            result.append((path, inspect(path)))
        except (OSError, ValueError, zipfile.BadZipFile):
            continue
    return result


def install(archive_path: Path, root: Path) -> tuple[str, list[Path]]:
    archive_path, root = Path(archive_path), Path(root)
    installed, total = [], 0
    metadata = inspect(archive_path, verify=True)
    with zipfile.ZipFile(archive_path) as archive:
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except Exception as exc:
            raise ValueError("manifest.json absent ou illisible") from exc
        if not isinstance(manifest, dict) or manifest.get("format") != "doot-pack":
            raise ValueError("ce fichier n'est pas un pack doot")
        name = safe_name(metadata["name"])
        for info in archive.infolist():
            parts = Path(info.filename).parts
            if info.is_dir() or len(parts) != 2 or parts[0] not in FOLDERS:
                continue
            if Path(info.filename).name != parts[1] or info.file_size > MAX_FILE:
                raise ValueError(f"entree dangereuse ou trop grande : {info.filename}")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("pack trop volumineux")
            directory = root / parts[0]
            directory.mkdir(parents=True, exist_ok=True)
            destination = _destination(directory, parts[1])
            with archive.open(info) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            installed.append(destination)
        if "config/profiles.json" in archive.namelist():
            from . import profiles

            try:
                raw_profiles = json.loads(archive.read("config/profiles.json")).get("profiles", {})
            except Exception:
                raw_profiles = {}
            if isinstance(raw_profiles, dict):
                existing = set(profiles.names(root / "profiles.json"))
                for profile_name, values in raw_profiles.items():
                    candidate = safe_name(profile_name)
                    base, number = candidate, 2
                    while candidate in existing:
                        candidate = f"{base}-{number}"
                        number += 1
                    try:
                        profiles.save(root / "profiles.json", candidate, values)
                    except (OSError, profiles.ProfileError):
                        continue
                    existing.add(candidate)
                    installed.append(root / "profiles.json")
    return name, installed
