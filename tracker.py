#!/usr/bin/env python3
"""
Habit Tracker CLI — Track your daily habits (skips, study, dumbbells, etc.)
Built by Quincy + Hermes | June 2026
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path

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


def log_habit(habit_name):
    """Record that you did a habit today."""
    data = load_data()
    today = str(date.today())

    if habit_name not in data:
        data[habit_name] = []

    if today not in data[habit_name]:
        data[habit_name].append(today)
        save_data(data)
        print(f"  ✅ Logged '{habit_name}' for {today}")
    else:
        print(f"  ⏭️  Already logged '{habit_name}' today!")


def show_today():
    """Show what you've done today."""
    data = load_data()
    today = str(date.today())
    done = [h for h in data if today in data[h]]

    print(f"\n  📅 Today ({today}):")
    if done:
        for h in done:
            print(f"    ✅ {h}")
    else:
        print("    ❌ Nothing logged yet today")


def show_streak(habit_name):
    """Show how many consecutive days you've done a habit."""
    data = load_data()
    dates = sorted(data.get(habit_name, []), reverse=True)

    if not dates:
        print(f"  No entries for '{habit_name}' yet.")
        return

    # Count consecutive days going back from today
    streak = 0
    check_date = date.today()
    
    for d in dates:
        if d == str(check_date):
            streak += 1
            check_date -= timedelta(days=1)
        elif d == str(check_date - timedelta(days=1)):
            # Allow yesterday if today isn't logged yet
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    print(f"\n  🔥 Streak for '{habit_name}': {streak} day{'s' if streak != 1 else ''}")
    print(f"  Total logs: {len(dates)}")


def show_week():
    """Show a simple weekly calendar of your habits."""
    data = load_data()
    today = date.today()

    print(f"\n  📊 This Week (starting {today - timedelta(days=6)}):")
    print()

    for habit in sorted(data.keys()):
        print(f"  {habit}:")
        line = "  "
        for i in range(6, -1, -1):
            d = str(today - timedelta(days=i))
            day_name = (today - timedelta(days=i)).strftime("%a")
            if d in data.get(habit, []):
                line += f"[{day_name[0]}]"
            else:
                line += f" . "
        print(line)
        print()


def menu():
    """Main menu loop."""
    while True:
        print("\n" + "=" * 40)
        print("   🏋️  HABIT TRACKER")
        print("=" * 40)
        print("1. Log a habit")
        print("2. Today's progress")
        print("3. View streak")
        print("4. This week overview")
        print("5. Exit")
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
            show_today()

        elif choice == "3":
            print("\n  Which habit streak?")
            for h in HABITS:
                print(f"    {h}")
            h_choice = input("  Pick (1-6): ").strip()
            if h_choice.isdigit() and 1 <= int(h_choice) <= len(HABITS):
                show_streak(HABITS[int(h_choice) - 1])
            else:
                print("  Invalid choice")

        elif choice == "4":
            show_week()

        elif choice == "5":
            print("\n  Keep going. See you tomorrow! 💪")
            break

        else:
            print("  Invalid choice")


if __name__ == "__main__":
    menu()
