# Import every tool module so their @mcp.tool() decorators run and register
# all tools on the shared mcp instance from gsheets_mcp.core.
from gsheets_mcp.tools import read
from gsheets_mcp.tools import write
from gsheets_mcp.tools import structure
from gsheets_mcp.tools import sheets
from gsheets_mcp.tools import format
from gsheets_mcp.tools import conditional
from gsheets_mcp.tools import validation
from gsheets_mcp.tools import protection
from gsheets_mcp.tools import charts
from gsheets_mcp.tools import named_ranges
from gsheets_mcp.tools import filters
from gsheets_mcp.tools import pivot
from gsheets_mcp.tools import metadata
from gsheets_mcp.tools import dashboard

__all__ = [
    'read', 'write', 'structure', 'sheets', 'format',
    'conditional', 'validation', 'protection', 'charts',
    'named_ranges', 'filters', 'pivot', 'metadata', 'dashboard',
]
