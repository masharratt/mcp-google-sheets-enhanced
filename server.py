#!/usr/bin/env python
"""
Google Spreadsheet MCP Server - thin shim.

This module preserves the entrypoint contract (server.mcp and server.main())
while delegating all logic to the gsheets_mcp package.
"""

from gsheets_mcp.core import mcp, main
import gsheets_mcp.tools  # triggers all @mcp.tool() decorator registrations

__all__ = ['mcp', 'main']
