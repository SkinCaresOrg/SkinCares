# Pytest plugin to ensure all tables are created in the test database before any tests run.

def pytest_configure():
    try:
        from deployment.api.db.init_db import init_db
        init_db()
    except Exception as e:
        print(f"[pytest setup] Failed to initialize test DB: {e}")
