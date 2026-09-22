"""Partitions visuelles d'apparitions : une timeline JSON sure et portable."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path


FORMATIONS = {"random", "canon", "wave", "rain", "vortex", "duel"}


@dataclass(frozen=True)
class Cue:
    at: float
    count: int = 1
    formation: str = "random"
    melody: str = ""


def safe_name(value: str) -> str:
    result = re.sub(r"[^\w-]+", "-", str(value).strip(), flags=re.UNICODE).strip("-_")
    if not result:
        raise ValueError("donne un nom a la choregraphie")
    return result[:64]


def validate(cues) -> list[Cue]:
    result = []
    if not isinstance(cues, (list, tuple)) or not cues:
        raise ValueError("ajoute au moins un repere")
    for raw in cues:
        raw = asdict(raw) if isinstance(raw, Cue) else raw
        if not isinstance(raw, dict):
            raise ValueError("repere illisible")
        at, count, formation = raw.get("at", 0), raw.get("count", 1), raw.get("formation", "random")
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not 0 <= float(at) <= 3600:
            raise ValueError("temps de repere attendu entre 0 et 3600 secondes")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 12:
            raise ValueError("chaque repere accepte de 1 a 12 doots")
        if formation not in FORMATIONS:
            raise ValueError("formation inconnue : " + str(formation))
        result.append(Cue(float(at), count, formation, str(raw.get("melody", ""))[:80]))
    return sorted(result, key=lambda cue: cue.at)


def save(directory: Path, name: str, cues) -> Path:
    cues = validate(cues)
    path = Path(directory) / f"{safe_name(name)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps({"format": "doot-choreography", "version": 1,
                                         "name": str(name), "cues": [asdict(cue) for cue in cues]},
                                        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    return path


def load(path: Path) -> tuple[str, list[Cue]]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("choregraphie illisible") from exc
    if not isinstance(raw, dict) or raw.get("format") != "doot-choreography":
        raise ValueError("ce fichier n'est pas une choregraphie Doot")
    return str(raw.get("name", Path(path).stem)), validate(raw.get("cues"))


def list_all(directory: Path) -> list[Path]:
    directory = Path(directory)
    return sorted(directory.glob("*.json")) if directory.is_dir() else []
