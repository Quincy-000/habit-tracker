import psycopg
import pytest

import tracker

TEST_DATABASE_URL = "postgresql://habits:habits@db:5432/habits_test"

tracker.DATABASE_URL = TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def reset_database():
    """Wipe and reseed the test database before every test."""
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE habits, logs RESTART IDENTITY CASCADE")
            cur.execute("""
                INSERT INTO habits (name) VALUES
                    ('Skips Morning (300)'),
                    ('Skips Evening (500)'),
                    ('AWS Study'),
                    ('Dumbbells'),
                    ('Reading'),
                    ('Other')
            """)
        conn.commit()
    yield
