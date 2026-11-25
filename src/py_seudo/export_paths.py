"""Dateinamen und Zielorte fuer Exporte.

Ausgabedateien uebernahmen frueher den Namen der Eingabedatei. E-Mails werden
aber oft nach dem Betreff benannt -- und der enthaelt nicht selten den
Patientennamen. Uebernommen wird der Name deshalb nur noch, wenn er wie eine
technische Dateikennung aussieht (ESOL0001, SLLA_0042 ...).
"""
from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from typing import Dict, Optional

_SAFE_STEM = re.compile(r"^(?:[A-Za-z]{2,8}[_-]?)?\d{1,10}$")
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,5}$")

_SYNC_MARKERS = (
    "onedrive", "dropbox", "google drive", "googledrive", "icloud", "nextcloud",
    "owncloud", "sharepoint", "box sync", "seafile", "tresorit",
)


def safe_stem(path: Optional[Path], fallback: str) -> str:
    """Dateistamm nur uebernehmen, wenn er keine Namen enthalten kann."""
    if path is not None and _SAFE_STEM.fullmatch(path.stem):
        return path.stem
    return fallback


def output_names(esol_path: Optional[Path], email_path: Optional[Path]) -> Dict[str, str]:
    """Neutrale Namen fuer ESOL, E-Mail und englischen Report."""
    esol_stem = safe_stem(esol_path, "abrechnung")
    esol_suffix = esol_path.suffix if esol_path is not None and _SAFE_SUFFIX.fullmatch(esol_path.suffix) else ""
    email_suffix = email_path.suffix.lower() if email_path is not None else ".eml"
    if email_suffix not in (".eml", ".txt"):
        email_suffix = ".eml"
    report_stem = esol_stem if esol_path is not None else safe_stem(email_path, "abrechnung")
    return {
        "esol": f"{esol_stem}_anonymisiert{esol_suffix}",
        "email": f"rueckmeldung_anonymisiert{email_suffix}",
        "report": f"{report_stem}_anonymisiert_summary_and_email_en.txt",
    }


def is_synced_location(path: Path) -> bool:
    """Zielordner, der vermutlich in eine Cloud oder auf ein Netzlaufwerk synchronisiert wird."""
    text = str(path)
    if text.startswith(("\\\\", "//")):  # UNC-Pfad: Netzlaufwerk
        return True
    parts = [p.lower() for p in PureWindowsPath(text).parts] + [p.lower() for p in Path(text).parts]
    return any(marker in part for part in parts for marker in _SYNC_MARKERS)
