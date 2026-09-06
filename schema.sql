CREATE TABLE habits (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE logs (
    id       SERIAL PRIMARY KEY,
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    log_date DATE NOT NULL,
    UNIQUE (habit_id, log_date)
);
