import sqlite3
import os
from datetime import datetime
from pathlib import Path

class DatabaseManager:
    def __init__(self):
        self.db_dir = Path.cwd() / "db"
        self.db_path = self.db_dir / "database.db"
        self._ensure_db_directory()
        self._initialize_db()

    def _ensure_db_directory(self):
            """Ensure the database directory exists."""
            try:
                self.db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating database directory: {e}")
                raise

    def _initialize_db(self):
        """Initialize the database and create required tables if they do not exist."""
        try:
            with sqlite3.connect(self.db_path) as connection:
                cursor = connection.cursor()

                # Character Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    main_file TEXT,
                    notes TEXT,
                    misc_notes TEXT,
                    created_date TEXT NOT NULL,
                    last_modified_date TEXT NOT NULL
                )
                """)

                # Extra Images Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS character_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_name TEXT NOT NULL,
                    image_note TEXT,
                    created_date TEXT NOT NULL,
                    last_modified_date TEXT NOT NULL,
                    character_id INTEGER NOT NULL,
                    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
                )
                """)

                # Lorebooks Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS lorebooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    notes TEXT,
                    misc_notes TEXT,
                    created_date TEXT NOT NULL,
                    last_modified_date TEXT NOT NULL
                )
                """)

                # Lorebook Images Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS lorebook_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lorebook_id INTEGER NOT NULL,
                    image_name TEXT UNIQUE NOT NULL,
                    image_note TEXT,
                    created_date TEXT NOT NULL,
                    last_modified_date TEXT NOT NULL,
                    FOREIGN KEY (lorebook_id) REFERENCES lorebooks (id) ON DELETE CASCADE
                )
                """)

                # Settings Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """)

                # Character Relationships Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS character_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id INTEGER NOT NULL,
                    related_character_id INTEGER NOT NULL,
                    FOREIGN KEY(character_id) REFERENCES characters(id) ON DELETE CASCADE,
                    FOREIGN KEY(related_character_id) REFERENCES characters(id) ON DELETE CASCADE
                )
                """)

                connection.commit()
                print("Database initialized successfully.")
        except sqlite3.Error as e:
            print(f"Error initializing the database: {e}")
            raise

    def get_setting(self, key, default=None):
        """Retrieve a setting from the database."""
        try:
            with sqlite3.connect(self.db_path) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                result = cursor.fetchone()
                return result[0] if result else default
        except sqlite3.Error as e:
            print(f"Error retrieving setting '{key}': {e}")
            return default

    def set_setting(self, key, value):
        """Set or update a setting in the database."""
        try:
            with sqlite3.connect(self.db_path) as connection:
                cursor = connection.cursor()
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (key, value))
                connection.commit()
                print(f"Setting '{key}' updated successfully.")
        except sqlite3.Error as e:
            print(f"Error setting '{key}': {e}")

    def add_character_to_db(self, name, main_file):
        """Add a new character to the database."""
        created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_modified_date = created_date

        try:
            with sqlite3.connect(self.db_path) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO characters (name, main_file, created_date, last_modified_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (name, main_file, created_date, last_modified_date)
                )
                connection.commit()
                print(f"Character '{name}' added successfully.")
        except sqlite3.Error as e:
            print(f"Error adding character '{name}': {e}")