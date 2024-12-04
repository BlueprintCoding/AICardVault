# extra_images.py
import os
import sqlite3
import shutil
from datetime import datetime
import customtkinter as ctk
from PIL import Image


class ExtraImagesManager:
    def __init__(self, master, db_path, get_character_name_callback, show_message_callback):
        self.master = master  # Main application window
        self.db_path = db_path  # Path to the database
        self.get_character_name = get_character_name_callback
        self.show_message = show_message_callback

    def load_extra_images(self, selected_character_id, extra_images_frame, create_thumbnail):
        """Load and display extra images for the selected character."""
        if not selected_character_id:
            print("No character selected for loading extra images.")
            return

        # Clear current images
        for widget in extra_images_frame.winfo_children():
            widget.destroy()

        # Fetch images from the database
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, image_name, image_note, created_date, last_modified_date FROM character_images WHERE character_id = ?",
            (selected_character_id,)
        )
        images = cursor.fetchall()
        connection.close()

        if not images:
            print("No extra images found for the selected character.")
            return

        for img_id, image_name, image_note, created_date, last_modified_date in images:
            frame = ctk.CTkFrame(extra_images_frame)
            frame.pack(fill="x", padx=5, pady=5)
            frame.grid_columnconfigure(0, weight=0)  # Image column
            frame.grid_columnconfigure(1, weight=1)  # Text and buttons column

            # Create thumbnail
            character_folder = os.path.join("CharacterCards", self.get_character_name(), "ExtraImages")
            image_path = os.path.join(character_folder, f"{image_name}.png")
            thumbnail = create_thumbnail(image_path)

            # Thumbnail Label
            thumbnail_label = ctk.CTkLabel(frame, image=thumbnail, text="")
            thumbnail_label.image = thumbnail  # Prevent garbage collection
            thumbnail_label.grid(row=0, column=0, rowspan=3, padx=5, pady=(5, 0), sticky="n")

            # Image Name
            name_label = ctk.CTkLabel(frame, text=image_name, anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
            name_label.grid(row=0, column=1, sticky="w", padx=5)

            # Process notes: remove clean breaks and wrap text
            truncated_notes = self._truncate_notes(image_note)
            notes_label = ctk.CTkLabel(
                frame,
                text=f"Notes: {truncated_notes}",
                anchor="w",
                font=ctk.CTkFont(size=10),
                wraplength=300  # Adjust this value as needed for wrapping width
            )
            notes_label.grid(row=1, column=1, sticky="w", padx=5)

            # Created Date
            created_label = ctk.CTkLabel(
                frame, text=f"Created: {self._format_date(created_date)}", anchor="w", font=ctk.CTkFont(size=10)
            )
            created_label.grid(row=2, column=1, sticky="w", padx=5)

            # Last Modified Date
            modified_label = ctk.CTkLabel(
                frame, text=f"Modified: {self._format_date(last_modified_date)}", anchor="w", font=ctk.CTkFont(size=10)
            )
            modified_label.grid(row=3, column=1, sticky="w", padx=5)

            # Edit and Delete Buttons
            edit_button = ctk.CTkButton(
                frame,
                text="View/Edit",
                width=80,
                command=lambda img_id=img_id: self.edit_image_notes(
                    img_id, selected_character_id, extra_images_frame, create_thumbnail
                ),
            )
            edit_button.grid(row=0, column=2, rowspan=1, padx=5, pady=(5, 0), sticky="e")

            delete_button = ctk.CTkButton(
                frame,
                text="Delete",
                width=80,
                fg_color="red",
                hover_color="darkred",
                command=lambda img_id=img_id: self.delete_image(
                    img_id, selected_character_id, extra_images_frame, create_thumbnail
                ),
            )
            delete_button.grid(row=1, column=2, rowspan=1, padx=5, pady=(5, 0), sticky="e")



    def save_image(self, selected_character_id, image_path_entry, image_name_entry, image_notes_textbox, extra_images_frame, create_thumbnail, modal_window):
        """Save the image to the character folder and database."""
        file_path = image_path_entry.get()
        image_name = image_name_entry.get().strip()
        image_note = image_notes_textbox.get("1.0", "end").strip()

        # Validate input
        if not file_path:
            self.show_message("Please select an image file.", "error")
            return
        if not image_name:
            self.show_message("Image name cannot be empty.", "error")
            return

        try:
            # Check for duplicate image name
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM character_images 
                WHERE image_name = ? AND character_id = ?
                """,
                (image_name, selected_character_id)
            )
            if cursor.fetchone()[0] > 0:
                self.show_message(f"Image name '{image_name}' already exists for this character.", "error")
                connection.close()
                return

            # Get the character's folder
            cursor.execute("SELECT name FROM characters WHERE id = ?", (selected_character_id,))
            result = cursor.fetchone()
            connection.close()

            if not result:
                self.show_message("Character folder not found.", "error")
                return

            character_name = result[0]
            character_folder = os.path.join("CharacterCards", character_name, "ExtraImages")
            os.makedirs(character_folder, exist_ok=True)

            # Copy the image to the folder
            image_path = os.path.join(character_folder, f"{image_name}.png")  # Assuming PNG format for simplicity
            shutil.copy(file_path, image_path)

            # Save metadata to the database
            created_date = last_modified_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO character_images (image_name, image_note, created_date, last_modified_date, character_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (image_name, image_note, created_date, last_modified_date, selected_character_id)
            )
            connection.commit()
            connection.close()

            # Immediately update the extra images UI
            self.load_extra_images(selected_character_id, extra_images_frame, create_thumbnail)

            # Show success message
            self.show_message("Image added successfully.", "success")

            # Close the modal window
            modal_window.destroy()

        except Exception as e:
            self.show_message(f"Failed to add image: {str(e)}", "error")


    def _truncate_notes(self, image_note):
        """Truncate notes to 150 characters while keeping clean breaks."""
        if image_note:
            clean_notes = "\n".join(filter(bool, image_note.splitlines()))
            if len(clean_notes) > 150:
                return clean_notes[:147] + "..."
            return clean_notes
        return "No notes provided"
    
    

    def edit_image_notes(self, image_id, selected_character_id, extra_images_frame, create_thumbnail):
        """Open a popup to edit image details."""
        # Fetch image details from the database
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT image_name, image_note, created_date, last_modified_date
            FROM character_images WHERE id = ?
            """,
            (image_id,),
        )
        result = cursor.fetchone()
        connection.close()

        if not result:
            self.show_message("Image not found.", "error")
            return

        image_name, image_note, created_date, last_modified_date = result

        # Create a modal window
        self.edit_image_window = ctk.CTkToplevel(self.master)
        self.edit_image_window.title("Edit Image")
        self.edit_image_window.geometry("400x300")

        # Ensure the modal stays on top of the main window
        self.edit_image_window.transient(self.master)  # Set to be a child of the main window
        self.edit_image_window.grab_set()  # Block interaction with the main window

        # Image Name Section
        name_frame = ctk.CTkFrame(self.edit_image_window)  # Create a frame for the row
        name_frame.pack(fill="x", pady=10, padx=10)

        name_label = ctk.CTkLabel(name_frame, text="Image Name:", anchor="w")
        name_label.pack(side="left", padx=5)

        self.edit_image_name_entry = ctk.CTkEntry(name_frame)
        self.edit_image_name_entry.insert(0, image_name)
        self.edit_image_name_entry.pack(side="left", padx=5)

        # Image Notes Section
        notes_label = ctk.CTkLabel(self.edit_image_window, text="Image Notes:", anchor="w")
        notes_label.pack(pady=10, padx=10, anchor="w")

        self.edit_image_notes_textbox = ctk.CTkTextbox(self.edit_image_window, height=100)
        self.edit_image_notes_textbox.insert("1.0", image_note)
        self.edit_image_notes_textbox.pack(fill="x", pady=0, padx=10)

        # Save Changes Button
        save_button = ctk.CTkButton(
            self.edit_image_window,
            text="Save Changes",
            command=lambda: self.save_image_changes(
                image_id, selected_character_id, extra_images_frame, create_thumbnail
            ),
        )
        save_button.pack(pady=10, padx=10)

        # Center the modal on the screen
        self.edit_image_window.update_idletasks()
        window_width = self.edit_image_window.winfo_width()
        window_height = self.edit_image_window.winfo_height()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        position_top = int((screen_height / 2) - (window_height / 2))
        position_right = int((screen_width / 2) - (window_width / 2))
        self.edit_image_window.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")

    def save_image_changes(self, image_id, selected_character_id, extra_images_frame, create_thumbnail):
        """Save changes to an image's details and rename the file if the name changes."""
        # Fetch updated data from the modal fields
        updated_image_name = self.edit_image_name_entry.get().strip()
        updated_image_note = self.edit_image_notes_textbox.get("1.0", "end").strip()

        # Validate input
        if not updated_image_name:
            self.show_message("Image name cannot be empty.", "error")
            return

        try:
            # Fetch the original image details
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT image_name, character_id FROM character_images WHERE id = ?",
                (image_id,)
            )
            result = cursor.fetchone()

            if not result:
                self.show_message("Image not found.", "error")
                connection.close()
                return

            original_image_name, character_id = result

            # Fetch the character name
            cursor.execute("SELECT name FROM characters WHERE id = ?", (character_id,))
            result = cursor.fetchone()

            if not result:
                self.show_message("Character folder not found.", "error")
                connection.close()
                return

            character_name = result[0]
            character_folder = os.path.join("CharacterCards", character_name, "ExtraImages")
            original_file_path = os.path.join(character_folder, f"{original_image_name}.png")
            updated_file_path = os.path.join(character_folder, f"{updated_image_name}.png")

            # Rename the file if the name has changed
            if original_image_name != updated_image_name:
                if os.path.exists(original_file_path):
                    os.rename(original_file_path, updated_file_path)
                    print(f"Renamed file: {original_file_path} -> {updated_file_path}")
                else:
                    print(f"Original file not found: {original_file_path}")
                    self.show_message("Original file not found. Unable to rename.", "error")
                    connection.close()
                    return

            # Update the database record
            query = """
                UPDATE character_images
                SET image_name = ?, image_note = ?, last_modified_date = ?
                WHERE id = ?
            """
            last_modified_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(query, (updated_image_name, updated_image_note, last_modified_date, image_id))

            # Commit changes and close the connection
            connection.commit()
            connection.close()

            # Refresh the extra images list in the UI
            self.load_extra_images(selected_character_id, extra_images_frame, create_thumbnail)

            # Close the modal window
            self.edit_image_window.destroy()

            # Show success message
            self.show_message("Image details updated successfully.", "success")
            print("Image details updated successfully")

        except Exception as e:
            self.show_message(f"Failed to save image changes: {str(e)}", "error")
            print(f"Failed to save image changes: {str(e)}")


    def delete_image(self, image_id, selected_character_id, extra_images_frame, create_thumbnail):
        """Delete an image from the character's folder and database with confirmation."""
        from tkinter.messagebox import askyesno

        # Show a confirmation prompt
        confirm = askyesno(
            title="Delete Image",
            message="Are you sure you want to delete this image? This action cannot be undone."
        )
        if not confirm:
            return  # Exit if the user cancels the deletion

        try:
            # Fetch the image details
            connection = sqlite3.connect(self.db_path)
            cursor = connection.cursor()

            cursor.execute("SELECT image_name, character_id FROM character_images WHERE id = ?", (image_id,))
            result = cursor.fetchone()

            if not result:
                self.show_message("Image not found.", "error")
                connection.close()
                return

            image_name, character_id = result

            # Fetch the character name
            cursor.execute("SELECT name FROM characters WHERE id = ?", (character_id,))
            result = cursor.fetchone()

            if not result:
                self.show_message("Character folder not found.", "error")
                connection.close()
                return

            character_name = result[0]
            character_folder = os.path.join("CharacterCards", character_name, "ExtraImages")
            image_path = os.path.join(character_folder, f"{image_name}.png")

            # Delete the image file
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted file: {image_path}")
            else:
                print(f"File not found: {image_path}")

            # Delete the database record
            cursor.execute("DELETE FROM character_images WHERE id = ?", (image_id,))
            connection.commit()
            connection.close()

            # Reload the extra images list
            self.load_extra_images(selected_character_id, extra_images_frame, create_thumbnail)

            # Show success message
            self.show_message("Image deleted successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to delete image: {str(e)}", "error")
            print(f"Failed to delete image: {str(e)}")


    def add_image_to_character(self):
        """Open a popup to add an image to the character."""
        # Fetch selected_character_id from the master (main class)
        selected_character_id = getattr(self.master, "selected_character_id", None)

        if not selected_character_id:
            self.show_message("No character selected to add an image.", "error")
            return

        # Create a modal window
        add_image_window = ctk.CTkToplevel(self.master)
        add_image_window.title("Add Image")
        add_image_window.geometry("400x300")

        # Ensure the modal stays on top of the main window
        add_image_window.transient(self.master)
        add_image_window.grab_set()

        # File Upload Section
        file_frame = ctk.CTkFrame(add_image_window)
        file_frame.pack(fill="x", pady=10, padx=10, anchor="w")

        file_label = ctk.CTkLabel(file_frame, text="Select Image:", anchor="w")
        file_label.pack(side="left", padx=5)

        image_path_entry = ctk.CTkEntry(file_frame, placeholder_text="Choose an image file", width=240)
        image_path_entry.pack(side="left", padx=5)

        browse_button = ctk.CTkButton(
            file_frame,
            text="Browse",
            width=100,
            command=lambda: self.browse_image_file(image_path_entry)
        )
        browse_button.pack(side="left", padx=5)

        # Image Name Section
        name_frame = ctk.CTkFrame(add_image_window)
        name_frame.pack(fill="x", pady=10, padx=10)

        name_label = ctk.CTkLabel(name_frame, text="Image Name:", anchor="w")
        name_label.pack(side="left", padx=5)

        image_name_entry = ctk.CTkEntry(name_frame, placeholder_text="", width=240)
        image_name_entry.pack(side="left", padx=5)

        # Image Notes Section
        notes_label = ctk.CTkLabel(add_image_window, text="Image Notes:", anchor="w")
        notes_label.pack(pady=10, padx=10, anchor="w")

        image_notes_textbox = ctk.CTkTextbox(add_image_window, height=100)
        image_notes_textbox.pack(fill="x", pady=0, padx=10)

        # Submit Button
        submit_button = ctk.CTkButton(
            add_image_window,
            text="Add Image",
            command=lambda: self.save_image(
                selected_character_id,  # Pass selected_character_id directly
                image_path_entry,
                image_name_entry,
                image_notes_textbox,
                self.master.extra_images_frame,  # Use the main app's extra_images_frame
                self.master.create_thumbnail,  # Use the main app's create_thumbnail method
                add_image_window  # Pass the modal window to close it after success
            )
        )
        submit_button.pack(pady=10, padx=10)

        # Center the modal on the screen
        self._center_modal(add_image_window)



    def browse_image_file(self, image_path_entry):
        """Open a file dialog to select an image and update the entry."""
        from tkinter.filedialog import askopenfilename
        file_path = askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if file_path:
            image_path_entry.delete(0, "end")
            image_path_entry.insert(0, file_path)


    @staticmethod
    def _format_date(date_str):
        """Format a date string to MM/DD/YYYY HH:MM (12hr format)."""
        if not date_str:
            return "Unknown Date"
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return date_obj.strftime("%m/%d/%Y %I:%M %p")
        except ValueError:
            return "Invalid Date"
        
    def _center_modal(self, window):
        """Center a modal window on the screen."""
        window.update_idletasks()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        screen_width = self.master.winfo_screenwidth()  # Use self.master for screen dimensions
        screen_height = self.master.winfo_screenheight()  # Use self.master for screen dimensions
        position_top = int((screen_height / 2) - (window_height / 2))
        position_right = int((screen_width / 2) - (window_width / 2))
        window.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")

