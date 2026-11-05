"""Test setup: the API tests use a throwaway SQLite database, never your real one."""
import os
import tempfile

_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_dir}/test.db"
