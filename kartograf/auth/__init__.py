"""
CLMS Authentication Proxy.

This module provides a secure proxy service for CLMS API authentication.
The proxy runs as a separate subprocess, isolating credentials from the
main application process.

Usage:
    The proxy is automatically started by CorineProvider when needed.
    Credentials are read from macOS Keychain by the proxy subprocess,
    never exposed to the main process.
"""

from kartograf.auth.client import AuthProxyClient

__all__ = ["AuthProxyClient"]
