from datetime import date, timedelta
import tracker


def test_load_data_no_file_returns_empty_dict():
    assert tracker.load_data() == {}


def test_save_and_load_data_roundtrip():
    with tracker.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM habits WHERE name = %s", ("Reading",))
            habit_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO logs (habit_id, log_date) VALUES (%s, %s), (%s, %s)",
                (habit_id, "2026-07-01", habit_id, "2026-07-02")
            )
        conn.commit()

    data = tracker.load_data()
    assert data["Reading"] == ["2026-07-01", "2026-07-02"]


def test_log_habit_first_time_adds_today():
    today = tracker.log_habit("Reading", verbose=False)
    data = tracker.load_data()
    assert today in data["Reading"]
    assert len(data["Reading"]) == 1


def test_log_habit_twice_same_day_does_not_duplicate():
    tracker.log_habit("Reading", verbose=False)
    tracker.log_habit("Reading", verbose=False)
    data = tracker.load_data()
    assert len(data["Reading"]) == 1


def test_get_today_status_splits_done_and_remaining():
    tracker.log_habit(tracker.HABITS[0], verbose=False)
    _, today, done, remaining = tracker.get_today_status()
    assert tracker.HABITS[0] in done
    assert tracker.HABITS[0] not in remaining
    assert len(done) + len(remaining) == len(tracker.HABITS)


def test_show_streak_no_entries_returns_zero():
    result = tracker.show_streak("Reading")
    assert result == 0


def test_show_streak_counts_consecutive_days():
    with tracker.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM habits WHERE name = %s", ("Reading",))
            habit_id = cur.fetchone()[0]
            today = date.today()
            dates = [today - timedelta(days=i) for i in range(3)]  # today, yesterday, 2 days ago
            for d in dates:
                cur.execute(
                    "INSERT INTO logs (habit_id, log_date) VALUES (%s, %s)",
                    (habit_id, d)
                )
        conn.commit()

    streak = tracker.show_streak("Reading")
    assert streak == 3


def test_show_streak_stops_at_gap():
    with tracker.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM habits WHERE name = %s", ("Reading",))
            habit_id = cur.fetchone()[0]
            today = date.today()
            dates = [today, today - timedelta(days=1), today - timedelta(days=5)]
            for d in dates:
                cur.execute(
                    "INSERT INTO logs (habit_id, log_date) VALUES (%s, %s)",
                    (habit_id, d)
                )
        conn.commit()

    streak = tracker.show_streak("Reading")
    assert streak == 2


def test_show_streak_zero_if_missed_today_and_yesterday():
    with tracker.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM habits WHERE name = %s", ("Reading",))
            habit_id = cur.fetchone()[0]
            today = date.today()
            cur.execute(
                "INSERT INTO logs (habit_id, log_date) VALUES (%s, %s)",
                (habit_id, today - timedelta(days=3))
            )
        conn.commit()

    streak = tracker.show_streak("Reading")
    assert streak == 0


def test_flask_home_route_returns_200():
    client = tracker.app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_flask_log_route_logs_habit_and_redirects():
    client = tracker.app.test_client()
    response = client.get("/log/1")
    assert response.status_code == 302  # redirect back to home
    data = tracker.load_data()
    assert tracker.HABITS[0] in data


def test_unlog_habit_removes_today_log():
    tracker.log_habit("Reading", verbose=False)
    assert "Reading" in tracker.load_data()
    assert tracker.unlog_habit("Reading") is True
    assert "Reading" not in tracker.load_data()


def test_unlog_habit_no_log_is_noop():
    assert tracker.unlog_habit("Reading") is False


def test_unlog_unknown_habit_returns_false():
    assert tracker.unlog_habit("No Such Habit") is False


def test_flask_unlog_route_removes_today_and_redirects():
    client = tracker.app.test_client()
    tracker.log_habit(tracker.HABITS[0], verbose=False)
    response = client.get("/unlog/1")
    assert response.status_code == 302  # redirect back to home
    assert tracker.HABITS[0] not in tracker.load_data()