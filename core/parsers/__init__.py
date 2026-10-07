"""
core/parsers/__init__.py
Arsitektur Adapter Parser untuk berbagai sumber data finansial (Fase 3A).
"""

from .base import BaseChannelParser
from .registry import ParserRegistry, default_registry

__all__ = ["BaseChannelParser", "ParserRegistry", "default_registry"]
