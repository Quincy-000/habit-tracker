import json
from datetime import date, timedelta
import pytest
import tracker


@pytest.fixture
def temp_data_file(tmp_path, monkeypatch):
    """Redirect tracker's DATA_FILE to a throwaway path so tests never touch real habit data."""
    fake_file = tmp_path / "habits.json"
    monkeypatch.setattr(tracker, "DATA_FILE", fake_file)
    return fake_file


def test_load_data_no_file_returns_empty_dict(temp_data_file):
    assert tracker.load_data() == {}


def test_save_and_load_data_roundtrip(temp_data_file):
    sample = {"Reading": ["2026-07-01", "2026-07-02"]}
    tracker.save_data(sample)
    assert tracker.load_data() == sample


def test_log_habit_first_time_adds_today(temp_data_file):
    today = tracker.log_habit("Reading", verbose=False)
    data = tracker.load_data()
    assert today in data["Reading"]
    assert len(data["Reading"]) == 1


def test_log_habit_twice_same_day_does_not_duplicate(temp_data_file):
    tracker.log_habit("Reading", verbose=False)
    tracker.log_habit("Reading", verbose=False)
    data = tracker.load_data()
    assert len(data["Reading"]) == 1


def test_get_today_status_splits_done_and_remaining(temp_data_file):
    tracker.log_habit(tracker.HABITS[0], verbose=False)
    _, today, done, remaining = tracker.get_today_status()
    assert tracker.HABITS[0] in done
    assert tracker.HABITS[0] not in remaining
    assert len(done) + len(remaining) == len(tracker.HABITS)


def test_show_streak_no_entries_returns_none(temp_data_file, capsys):
    result = tracker.show_streak("Reading")
    assert result is None


def test_show_streak_counts_consecutive_days(temp_data_file):
    today = date.today()
    dates = [str(today - timedelta(days=i)) for i in range(3)]  # today, yesterday, 2 days ago
    tracker.save_data({"Reading": dates})
    streak = tracker.show_streak("Reading")
    assert streak == 3


def test_show_streak_stops_at_gap(temp_data_file):
    today = date.today()
    dates = [str(today), str(today - timedelta(days=1)), str(today - timedelta(days=5))]
    tracker.save_data({"Reading": dates})
    streak = tracker.show_streak("Reading")
    assert streak == 2


def test_show_streak_zero_if_missed_today_and_yesterday(temp_data_file):
    today = date.today()
    dates = [str(today - timedelta(days=3))]
    tracker.save_data({"Reading": dates})
    streak = tracker.show_streak("Reading")
    assert streak == 0


def test_flask_home_route_returns_200(temp_data_file):
    client = tracker.app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_flask_log_route_logs_habit_and_redirects(temp_data_file):
    client = tracker.app.test_client()
    response = client.get("/log/1")
    assert response.status_code == 302  # redirect back to home
    data = tracker.load_data()
    assert tracker.HABITS[0] in data