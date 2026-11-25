"""API-Schluessel verschluesselt ablegen.

Unter Windows landen QSettings in der Registry (HKCU). Ohne Verschluesselung
kann jeder Prozess des Benutzers die Schluessel dort auslesen. Hier werden sie
mit der Windows-Datenschutz-API (DPAPI, ``CryptProtectData``) an das
Benutzerkonto gebunden verschluesselt -- ohne zusaetzliche Abhaengigkeit.

Auf anderen Systemen (CI, Entwicklung unter Linux/macOS) steht DPAPI nicht zur
Verfuegung; dort wird der Wert mit dem Praefix ``plain:`` gespeichert und
:func:`is_secure` liefert ``False``, damit die Oberflaeche darauf hinweisen kann.
"""
from __future__ import annotations

import base64
import sys
from typing import Tuple

PREFIX_DPAPI = "dpapi:"
PREFIX_PLAIN = "plain:"
_ENTROPY = b"py-seudo api key"


def is_secure() -> bool:
    """True, wenn Schluessel verschluesselt gespeichert werden koennen."""
    return sys.platform == "win32"


def _dpapi(data: bytes, protect: bool) -> bytes:  # pragma: no cover - nur Windows
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def blob(raw: bytes) -> Tuple[DATA_BLOB, ctypes.Array]:
        buf = ctypes.create_string_buffer(raw, len(raw))
        return DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    blob_in, _keep_in = blob(data)
    entropy, _keep_entropy = blob(_ENTROPY)
    blob_out = DATA_BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x01

    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(blob_in), "py-seudo", ctypes.byref(entropy),
            None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, ctypes.byref(entropy),
            None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out),
        )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))


def protect(secret: str) -> str:
    """Schluessel fuer die Ablage vorbereiten."""
    if not secret:
        return ""
    if is_secure():
        encrypted = _dpapi(secret.encode("utf-8"), protect=True)
        return PREFIX_DPAPI + base64.b64encode(encrypted).decode("ascii")
    return PREFIX_PLAIN + secret


def unprotect(stored: str) -> Tuple[str, bool]:
    """Gespeicherten Wert lesen.

    Returns:
        (schluessel, muss_neu_gespeichert_werden). Das zweite Feld ist True fuer
        Altbestaende, die noch unverschluesselt in der Registry stehen.
    """
    if not stored:
        return "", False
    if stored.startswith(PREFIX_DPAPI):
        if not is_secure():
            return "", False
        try:
            raw = base64.b64decode(stored[len(PREFIX_DPAPI):])
            return _dpapi(raw, protect=False).decode("utf-8"), False
        except Exception:  # noqa: BLE001 -- unlesbar (anderer Benutzer/Rechner): verwerfen
            return "", False
    if stored.startswith(PREFIX_PLAIN):
        return stored[len(PREFIX_PLAIN):], is_secure()
    # Altbestand aus Versionen vor der Verschluesselung
    return stored, True
