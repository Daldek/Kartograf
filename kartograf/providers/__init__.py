"""
Providers module for Kartograf.

This module contains provider implementations for downloading data
from various sources. Currently supported providers:

- GugikProvider: Downloads NMT data from GUGiK (Polish geodesy service)
"""

from kartograf.providers.base import BaseProvider
from kartograf.providers.gugik import GugikProvider

__all__ = ["BaseProvider", "GugikProvider"]
