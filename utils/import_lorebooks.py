import os
import sqlite3
from datetime import datetime
import shutil
from pathlib import Path

class LorebookManager:
    def __init__(self, sillytavern_path, db_path):
        self.sillytavern_path = sillytavern_path
        self.lorebooks_path = "Lorebooks"  # Folder in the root directory
        self.db_path = db_path
        self.worlds_path = Path(self.sillytavern_path) / "worlds"
        Path(self.lorebooks_path).mkdir(parents=True, exist_ok=True)  # Ensure the Lorebooks folder exists

    def sync_lorebooks(self):
        """Sync lorebooks from SillyTavern to the Lorebooks folder and database."""
        if not self.worlds_path.exists():
            print("SillyTavern worlds folder not found.")
            return

        try:
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()

            # Ensure the lorebooks table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lorebooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    notes TEXT,
                    misc_notes TEXT,
                    created_date TEXT,
                    last_modified_date TEXT
                )
            """)
            connection.commit()

            new_lorebooks_added = False

            # Iterate through all JSON files in the worlds folder
            for json_file in self.worlds_path.glob("*.json"):
                lorebook_name = json_file.stem  # Extract the name without extension
                target_folder = Path(self.lorebooks_path) / lorebook_name

                # Create a folder for the lorebook
                target_folder.mkdir(parents=True, exist_ok=True)

                # Check if the lorebook is already in the database
                cursor.execute("SELECT COUNT(*) FROM lorebooks WHERE filename = ?", (json_file.name,))
                exists = cursor.fetchone()[0]

                if not exists:
                    # Add the lorebook to the database
                    created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("""
                        INSERT INTO lorebooks (filename, notes, misc_notes, created_date, last_modified_date)
                        VALUES (?, ?, ?, ?, ?)
                    """, (json_file.name, "", "", created_date, created_date))
                    connection.commit()
                    new_lorebooks_added = True
                    print(f"Lorebook added to DB: {json_file.name}")

            if new_lorebooks_added:
                print("New lorebooks synced successfully.")
            else:
                print("No new lorebooks found to sync.")

        except Exception as e:
            print(f"Error syncing lorebooks: {str(e)}")

        finally:
            connection.close()



    def get_lorebooks_list(self):
        """Retrieve lorebooks from the database."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT id, filename, notes, misc_notes, created_date, last_modified_date FROM lorebooks")
        rows = cursor.fetchall()
        connection.close()

        return [
            {
                "id": row[0],
                "filename": row[1],
                "notes": row[2],
                "misc_notes": row[3],
                "created_date": row[4],
                "last_modified_date": row[5],
            }
            for row in rows
        ]


    def save_lorebook_changes(self, notes, misc_notes, filename, refresh_lorebooks_callback=None):
        """Save changes to the lorebook in the database."""
        try:
            connection = sqlite3.connect(self.db_path)  # Use self.db_path directly
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE lorebooks SET notes = ?, misc_notes = ?, last_modified_date = ?
                WHERE filename = ?
                """,
                (notes, misc_notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename)
            )
            connection.commit()
            connection.close()

            # Call refresh callback if provided
            if refresh_lorebooks_callback:
                refresh_lorebooks_callback()

            return "Lorebook changes saved successfully."
        except Exception as e:
            print(f"Error saving lorebook changes: {e}")
            return f"Failed to save lorebook changes: {str(e)}"


    def load_images(self, lorebook_id):
        """Load images associated with a lorebook."""
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, image_name, image_note, created_date, last_modified_date FROM lorebook_images WHERE lorebook_id = ?",
            (lorebook_id,)
        )
        images = cursor.fetchall()
        connection.close()
        return images

    def save_image(self, lorebook_id, image_name, image_note, file_path, modal=None, refresh_callback=None):
        """Save a new image to the lorebook."""
        try:
            # Save image metadata to the database
            created_date = last_modified_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO lorebook_images (lorebook_id, image_name, image_note, created_date, last_modified_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (lorebook_id, image_name, image_note, created_date, last_modified_date)
            )
            connection.commit()

            # Retrieve the lorebook folder name
            cursor.execute("SELECT filename FROM lorebooks WHERE id = ?", (lorebook_id,))
            lorebook_row = cursor.fetchone()
            connection.close()

            if not lorebook_row:
                raise Exception("Lorebook folder not found for the given ID.")
            
            # Strip extension and determine paths
            lorebook_name = Path(lorebook_row[0]).stem  # Strip extension
            lorebook_folder = Path("Lorebooks") / lorebook_name / "images"  # Path to images folder

            # Create the images folder if it doesn't exist
            lorebook_folder.mkdir(parents=True, exist_ok=True)

            # Copy the file to the images folder
            shutil.copy(file_path, lorebook_folder / f"{image_name}.png")

            # Invoke the refresh callback and close the modal if provided
            if refresh_callback:
                refresh_callback()
            if modal:
                modal.destroy()

            print("Image saved successfully.")
            return True
        except Exception as e:
            print(f"Error saving image: {e}")
            return False

    def delete_image(self, image_id, lorebook_id):
        """Delete an image from the database and disk."""
        try:
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute("SELECT image_name FROM lorebook_images WHERE id = ?", (image_id,))
            result = cursor.fetchone()
            if not result:
                raise Exception("Image not found in database.")

            image_name = result[0]

            # Get the lorebook folder
            cursor.execute("SELECT filename FROM lorebooks WHERE id = ?", (lorebook_id,))
            lorebook_row = cursor.fetchone()
            if not lorebook_row:
                raise Exception("Lorebook folder not found for the given ID.")

            # Strip extension and determine the image path
            lorebook_name = Path(lorebook_row[0]).stem  # Strip extension
            image_path = Path("Lorebooks") / lorebook_name / "images" / f"{image_name}.png"

            # Delete the image file if it exists
            if image_path.exists():
                image_path.unlink()
                print(f"Deleted image: {image_path}")
            else:
                print(f"Image not found: {image_path}")

            # Delete the image entry in the database
            cursor.execute("DELETE FROM lorebook_images WHERE id = ?", (image_id,))
            connection.commit()
            connection.close()

            print(f"Image {image_name} deleted successfully.")
            return True
        except Exception as e:
            print(f"Error deleting image: {e}")
            return False
            
    def get_image_details(self, image_id):
        """Retrieve image details from the database."""
        try:
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT image_name, image_note, created_date, last_modified_date
                FROM lorebook_images
                WHERE id = ?
                """,
                (image_id,)
            )
            result = cursor.fetchone()
            connection.close()
            return result if result else None
        except Exception as e:
            print(f"Error retrieving image details: {e}")
            return None

            
    def update_image_details(self, image_id, new_image_name, new_image_note):
        """Update the image details in the database."""
        try:
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE lorebook_images
                SET image_name = ?, image_note = ?, last_modified_date = ?
                WHERE id = ?
                """,
                (new_image_name, new_image_note, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), image_id)
            )
            connection.commit()
            connection.close()
            return True
        except Exception as e:
            print(f"Error updating image details: {e}")
            return False
