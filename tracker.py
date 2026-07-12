#!/usr/bin/env python3
"""
Habit Tracker CLI + Flask web app — Track your daily habits (skips, study, dumbbells, etc.)
Built by Quincy + Hermes | June 2026
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, render_template, redirect, url_for

DATA_FILE = Path.home() / ".habits.json"

# Default habits you can track
HABITS = [
    "1. Skips Morning (300)",
    "2. Skips Evening (500)",
    "3. AWS Study",
    "4. Dumbbells",
    "5. Reading",
    "6. Other"
]

app = Flask(__name__)


def load_data():
    """Load saved habits from JSON file."""
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}


def save_data(data):
    """Save habits to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def log_habit(habit_name, verbose=True):
    """Record that you did a habit today."""
    data = load_data()
    today = str(date.today())

    if habit_name not in data:
        data[habit_name] = []

    if today not in data[habit_name]:
        data[habit_name].append(today)
        save_data(data)
        if verbose:
            print(f"  ✅ Logged '{habit_name}' for {today}")
    else:
        if verbose:
            print(f"  ⏭️  Already logged '{habit_name}' today!")

    return today


def get_today_status():
    """Return the current day's habits and remaining habits."""
    data = load_data()
    today = str(date.today())
    done = [habit for habit in HABITS if today in data.get(habit, [])]
    remaining = [habit for habit in HABITS if habit not in done]
    return data, today, done, remaining


def show_today():
    """Show what you've done today in the CLI."""
    _, today, done, remaining = get_today_status()

    print(f"\n  📅 Today ({today}):")
    if done:
        for h in done:
            print(f"    ✅ {h}")
    else:
        print("    ❌ Nothing logged yet today")

    if remaining:
        print(f"  Remaining ({len(remaining)}):")
        for h in remaining:
            print(f"    ⬜ {h}")


def show_streak(habit_name):
    """Show how many consecutive days you've done a habit."""
    data = load_data()
    dates = sorted(data.get(habit_name, []), reverse=True)

    if not dates:
        print(f"  No entries for '{habit_name}' yet.")
        return

    streak = 0
    check_date = date.today()

    for d in dates:
        if d == str(check_date):
            streak += 1
            check_date -= timedelta(days=1)
        elif d == str(check_date - timedelta(days=1)):
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    print(f"\n  🔥 Streak for '{habit_name}': {streak} day{'s' if streak != 1 else ''}")
    print(f"  Total logs: {len(dates)}")
    return streak


def show_week():
    """Show a weekly calendar of your habits."""
    data = load_data()
    today = date.today()

    print(f"\n  📊 Last 7 Days ({(today - timedelta(days=6)).strftime('%a %d')} → {today.strftime('%a %d')}):")
    print()

    all_habits = sorted(data.keys())
    if not all_habits:
        print("  No habits logged yet. Start by logging something!")
        return

    header = "        "
    day_labels = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        header += f" {d.strftime('%a')} "
        day_labels.append(str(d))
    print(header)
    print()

    for habit in all_habits:
        short_name = habit
        if len(short_name) > 21:
            short_name = short_name[:18] + "..."

        line = f"  {short_name:21s}"
        for dl in day_labels:
            if dl in data.get(habit, []):
                line += "  ✅"
            else:
                line += "  ··"
        print(line)

    print()
    show_today_summary(data, today, day_labels)


def show_today_summary(data, today, day_labels):
    """Show summary stats for the week."""
    print(f"  ── Stats ──")
    for habit in sorted(data.keys()):
        week_count = sum(1 for d in day_labels if d in data[habit])
        bar = "█" * week_count + "░" * (7 - week_count)
        print(f"  {bar} {habit} ({week_count}/7)")


def menu():
    """Main menu loop."""
    while True:
        print("\n" + "=" * 40)
        print("   🏋️  HABIT TRACKER")
        print("=" * 40)
        show_today()
        print()
        print("   [1] Log a habit")
        print("   [2] View streak for a habit")
        print("   [3] This week overview")
        print("   [4] Big picture (all habits over time)")
        print("   [5] Exit")
        print("=" * 40)

        choice = input("  Choose (1-5): ").strip()

        if choice == "1":
            print("\n  Which habit did you do?")
            for h in HABITS:
                print(f"    {h}")
            h_choice = input("  Pick (1-6): ").strip()
            if h_choice.isdigit() and 1 <= int(h_choice) <= len(HABITS):
                log_habit(HABITS[int(h_choice) - 1])
            else:
                print("  Invalid choice")

        elif choice == "2":
            print("\n  Which habit streak?")
            for h in HABITS:
                print(f"    {h}")
            h_choice = input("  Pick (1-6): ").strip()
            if h_choice.isdigit() and 1 <= int(h_choice) <= len(HABITS):
                show_streak(HABITS[int(h_choice) - 1])
            else:
                print("  Invalid choice")

        elif choice == "3":
            show_week()

        elif choice == "4":
            show_all_time()

        elif choice == "5":
            print("\n  Keep going. See you tomorrow! 💪")
            break

        else:
            print("  Invalid choice")


def show_all_time():
    """Show all-time logging summary."""
    data = load_data()
    if not data:
        print("\n  No data yet. Start tracking!")
        return

    print("\n  📈 Big Picture (All Time)")
    print()
    for habit in sorted(data.keys()):
        dates = sorted(data[habit])
        total = len(dates)
        first = dates[0]
        last = dates[-1]
        unique_days = len(set(dates))
        first_date = date.fromisoformat(first)
        days_since = (date.today() - first_date).days + 1
        rate = f"{unique_days / days_since * 100:.0f}%" if days_since > 0 else "N/A"

        print(f"  {habit}")
        print(f"    Total: {total} logs across {unique_days} unique days")
        print(f"    First: {first}  |  Last: {last}")
        print(f"    Hit rate: {rate} of days")
        print()


def fast_log(habit_name):
    """Direct log without the menu (for CLI args)."""
    data = load_data()
    today = str(date.today())

    if habit_name not in data:
        data[habit_name] = []

    if today not in data[habit_name]:
        data[habit_name].append(today)
        save_data(data)
        print(f"  ✅ Logged '{habit_name}'")
    else:
        print(f"  ⏭️  Already logged '{habit_name}' today")


@app.route("/")
def home():
    _, today, done, remaining = get_today_status()
    return render_template("index.html", habits=HABITS, done=done, remaining=remaining, today=today)


@app.route("/log/<int:habit_id>")
def log_route(habit_id):
    if 1 <= habit_id <= len(HABITS):
        log_habit(HABITS[habit_id - 1], verbose=False)
    return redirect(url_for("home"))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "web":
        app.run(debug=True, host="0.0.0.0", port=5000)

    elif len(sys.argv) >= 3 and sys.argv[1] == "log":
        habit_input = " ".join(sys.argv[2:])
        if habit_input.isdigit() and 1 <= int(habit_input) <= len(HABITS):
            fast_log(HABITS[int(habit_input) - 1])
        elif habit_input in HABITS:
            fast_log(habit_input)
        else:
            matches = [h for h in HABITS if habit_input.lower() in h.lower()]
            if len(matches) == 1:
                fast_log(matches[0])
            elif len(matches) > 1:
                print(f"  Multiple matches: {matches}")
            else:
                print(f"  Habit '{habit_input}' not found. Available:")
                for h in HABITS:
                    print(f"    {h}")

    elif len(sys.argv) >= 2 and sys.argv[1] == "today":
        show_today()

    elif len(sys.argv) >= 2 and sys.argv[1] == "week":
        show_week()

    elif len(sys.argv) >= 2 and sys.argv[1] == "streak":
        if len(sys.argv) >= 3:
            habit_input = " ".join(sys.argv[2:])
            if habit_input.isdigit() and 1 <= int(habit_input) <= len(HABITS):
                show_streak(HABITS[int(habit_input) - 1])
            elif habit_input in HABITS:
                show_streak(habit_input)
            else:
                matches = [h for h in HABITS if habit_input.lower() in h.lower()]
                if len(matches) == 1:
                    show_streak(matches[0])
                elif len(matches) > 1:
                    print(f"  Multiple matches: {matches}")
                else:
                    print(f"  Habit '{habit_input}' not found.")
        else:
            print("  Usage: python tracker.py streak <habit name or number>")

    elif len(sys.argv) >= 2 and sys.argv[1] == "all":
        show_all_time()

    else:
        menu()
