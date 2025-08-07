"""
Run As User
-----------

A Python utility to run commands as the currently logged-in user 
from a high-privilege context (e.g., SYSTEM), with full stdio redirection.
"""

__version__ = "0.1.0"

from .main import run_as_current_user

__all__ = ["run_as_current_user"]
