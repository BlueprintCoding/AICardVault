import sqlite3
import os

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
            name TEXT UNIQUE,
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

        connection.commit()
        connection.close()
