"""
Backend package root.

Having `src` as an explicit Python package helps ensure absolute imports like
`from src.db.session import get_db` work reliably in all environments.
"""
