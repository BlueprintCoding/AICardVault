import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.db_dir = os.path.join(os.getcwd(), "db")
        self.db_path = os.path.join(self.db_dir, "database.db")
        self._ensure_db_directory()
        self._initialize_db()

    def _ensure_db_directory(self):
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir)

    def _initialize_db(self):
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()

        # Character Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            main_file TEXT,
            notes TEXT,
            misc_notes TEXT,
            created_date TEXT,
            last_modified_date TEXT
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
        FOREIGN KEY (character_id) REFERENCES characters (id)
        )
        """)

        # Lorebooks Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lorebooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER,
            file_path TEXT,
            notes TEXT,
            FOREIGN KEY(character_id) REFERENCES characters(id)
        )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
         
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id INTEGER NOT NULL,
            related_character_id INTEGER NOT NULL,
            FOREIGN KEY(character_id) REFERENCES characters(id),
            FOREIGN KEY(related_character_id) REFERENCES characters(id)
            )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('character', 'model_api'))
            )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS character_tags (
            character_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE,
            UNIQUE(character_id, tag_id)
        )
        """)


        connection.commit()
        connection.close()

    def get_setting(self, key, default=None):
        """Retrieve a setting from the database."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        connection.close()
        return result[0] if result else default

    def set_setting(self, key, value):
        """Set or update a setting in the database."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        connection.commit()
        connection.close()

    def add_character_to_db(self, name, main_file):
        """Add a new character to the database."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()

        created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_modified_date = created_date

        cursor.execute(
            """
            INSERT INTO characters (name, main_file, created_date, last_modified_date)
            VALUES (?, ?, ?, ?)
            """,
            (name, main_file, created_date, last_modified_date)
        )
        connection.commit()
        connection.close()
