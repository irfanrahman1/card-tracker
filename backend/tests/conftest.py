"""Test setup: the API tests use a throwaway database (SQLite by default), never your real one."""
import os
import tempfile

_db_dir = tempfile.mkdtemp()
# Set TEST_DATABASE_URL to run the same tests against Postgres (like production).
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_db_dir}/test.db"
