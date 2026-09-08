"""Email sanitization package."""
from py_seudo.email.anonymizer import EmailAnonymizer
from py_seudo.email.names import NameDetector, NameHit, NameRole

__all__ = ["EmailAnonymizer", "NameDetector", "NameHit", "NameRole"]
