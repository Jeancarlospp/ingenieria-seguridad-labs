CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'teacher'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS user_subjects (
    user_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, subject_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    subject_id INTEGER NOT NULL,
    owner_id INTEGER NOT NULL,
    audience TEXT NOT NULL
        CHECK (audience IN ('students', 'teachers')),
    storage_name TEXT UNIQUE NOT NULL,
    original_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (owner_id) REFERENCES users(id)
);