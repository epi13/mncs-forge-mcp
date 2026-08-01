"""MNCS Forge MCP experimental reference implementation."""

__version__ = "0.1.0a2"

# Load the hardened lifecycle before engine.py imports the public service class.
# This keeps the original service available as the stable implementation base while
# moving deletion, terminal-record, and heterogeneous-batch policy into focused modules.
from . import micro_verifiers as _micro_verifiers
from .micro_verifiers_hardened import HardenedMicroVerifierService

vars(_micro_verifiers)["MicroVerifierService"] = HardenedMicroVerifierService
