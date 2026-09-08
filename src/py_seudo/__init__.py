"""py-seudo: DSGVO-konforme Pseudonymisierung von ESOL-Abrechnungsdateien und Rückmeldungsemails."""
from py_seudo.engine import PseudoEngine
from py_seudo.models import AnonymizationResult, MappingEntry, ReplacementCategory

__version__ = "0.1.0"

__all__ = [
    "AnonymizationResult",
    "MappingEntry",
    "PseudoEngine",
    "ReplacementCategory",
    "__version__",
]
