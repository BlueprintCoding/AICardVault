import customtkinter as ctk
from PIL import Image, ImageTk
import os
import shutil
import sqlite3
from utils.db_manager import DatabaseManager
from utils.file_handler import FileHandler
from datetime import datetime
from utils.extra_images import ExtraImagesManager

class CharacterCardManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Character Card Manager")
        self.geometry("1200x700")
        ctk.set_appearance_mode("System")  # Use system theme
        ctk.set_default_color_theme("blue")  # Default color theme

        # Initialize database and file handler
        self.db_manager = DatabaseManager()
        self.file_handler = FileHandler()
        
                # Initialize ExtraImagesManager
        self.extra_images_manager = ExtraImagesManager(
            self,  # Pass the main app window as master
            db_path=self.db_manager.db_path,
            get_character_name_callback=self.get_character_name,
            show_message_callback=self.show_message,
        )

        # Layout
        self.grid_columnconfigure(0, weight=1)  # Sidebar grows slightly
        self.grid_columnconfigure(1, weight=2)  # Character list grows moderately
        self.grid_columnconfigure(2, weight=5)  # Edit panel grows the most
        self.grid_rowconfigure(0, weight=1)     # Allow row to stretch vertically

        # Create UI components
        self.create_sidebar()
        self.create_character_list()
        self.create_edit_panel()


    def load_extra_images(self):
        """Delegate to ExtraImagesManager."""
        self.extra_images_manager.load_extra_images(
            self.selected_character_id,
            self.extra_images_frame,
            self.create_thumbnail
        )


    def create_sidebar(self):
        """Create the sidebar with menu options."""
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nswe")

        # Sidebar Title
        sidebar_label = ctk.CTkLabel(self.sidebar, text="Menu", font=ctk.CTkFont(size=18, weight="bold"))
        sidebar_label.pack(pady=10)

        # Buttons in the sidebar
        self.add_character_button = ctk.CTkButton(self.sidebar, text="Add Character", command=self.add_character)
        self.add_character_button.pack(pady=10, padx=10, fill="x")

        self.import_button = ctk.CTkButton(self.sidebar, text="Import Data", command=self.import_data)
        self.import_button.pack(pady=10, padx=10, fill="x")

        self.export_button = ctk.CTkButton(self.sidebar, text="Export Data", command=self.export_data)
        self.export_button.pack(pady=10, padx=10, fill="x")

        self.settings_button = ctk.CTkButton(self.sidebar, text="Settings", command=self.open_settings)
        self.settings_button.pack(pady=10, padx=10, fill="x")

    def create_character_list(self):
        """Create the middle column for the character list."""
        self.character_list_frame = ctk.CTkFrame(self)
        self.character_list_frame.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)

        # Title
        list_label = ctk.CTkLabel(self.character_list_frame, text="Character List", font=ctk.CTkFont(size=14, weight="bold"))
        list_label.pack(pady=10)

        # Scrollable Frame for Characters
        self.scrollable_frame = ctk.CTkScrollableFrame(self.character_list_frame)
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Load characters (Example: Replace with actual database data)
        characters = self.get_character_list()
        for char in characters:
            self.add_character_to_list(char)

    def get_character_list(self):
        """Retrieve the list of characters from the database."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, name, main_file, created_date, last_modified_date FROM characters"
        )
        characters = cursor.fetchall()
        connection.close()

        # Convert to a list of dictionaries
        return [
            {
                "id": row[0],
                "name": row[1],
                "image_path": os.path.join("CharacterCards", row[1], row[2]),
                "created_date": row[3],
                "last_modified_date": row[4]
            }
            for row in characters
        ]

    def add_character_to_list(self, character):
        """Add a character entry to the list with a thumbnail image."""
        char_frame = ctk.CTkFrame(self.scrollable_frame, corner_radius=5)
        char_frame.character_id = character["id"]  # Assign the character ID
        char_frame.character_name = character["name"]  # Assign the character name
        char_frame.pack(pady=5, padx=5, fill="x")
        
        image_path = character.get("image_path", "assets/default_thumbnail.png")
        created_date = character.get("created_date", "Unknown Date")
        last_modified_date = character.get("last_modified_date", "Unknown Date")

        # Reformat the created_date to MM/DD/YYYY HH:MM (12hr format)
        if created_date != "Unknown Date":
            created_date_obj = datetime.strptime(created_date, "%Y-%m-%d %H:%M:%S")
            formatted_created_date = created_date_obj.strftime("%m/%d/%Y %I:%M %p")
        else:
            formatted_created_date = created_date

        # Reformat the last_modified_date to MM/DD/YYYY HH:MM (12hr format)
        if last_modified_date != "Unknown Date":
            last_modified_date_obj = datetime.strptime(last_modified_date, "%Y-%m-%d %H:%M:%S")
            formatted_last_modified_date = last_modified_date_obj.strftime("%m/%d/%Y %I:%M %p")
        else:
            formatted_last_modified_date = last_modified_date

        # Use grid for layout inside char_frame
        char_frame.grid_columnconfigure(0, weight=0)  # Fixed size for image column
        char_frame.grid_columnconfigure(1, weight=1)  # Flexible size for text column

        # Create a frame for the image
        image_frame = ctk.CTkFrame(char_frame, width=50, height=75, fg_color="transparent")
        image_frame.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky="n")  # Align top

        # Add thumbnail
        thumbnail = self.create_thumbnail(image_path)
        thumbnail_label = ctk.CTkLabel(image_frame, image=thumbnail, text="")
        thumbnail_label.image = thumbnail
        thumbnail_label.pack()

        # Bind the click event to the thumbnail
        thumbnail_label.bind(
            "<Button-1>",
            lambda e, char_id=character["id"]: self.select_character_by_id(char_id),
        )

        # Add text directly to char_frame
        name_label = ctk.CTkLabel(char_frame, text=character["name"], anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        name_label.grid(row=0, column=1, sticky="w", padx=5, pady=(0, 0))  # Top padding for spacing

        created_date_label = ctk.CTkLabel(
            char_frame, text=f"Created: {formatted_created_date}", anchor="w", font=ctk.CTkFont(size=12)
        )
        created_date_label.grid(row=1, column=1, sticky="w", padx=5, pady=(0, 0))  # Minimal vertical padding

        modified_date_label = ctk.CTkLabel(
            char_frame, text=f"Last Modified: {formatted_created_date}", anchor="w", font=ctk.CTkFont(size=12)
        )
        modified_date_label.grid(row=2, column=1, sticky="w", padx=5, pady=(0, 0))  # Minimal vertical padding

        # Add click event for selection to the entire frame and its children
        widgets_to_bind = [char_frame, thumbnail_label, name_label, created_date_label, modified_date_label]
        for widget in widgets_to_bind:
            widget.bind("<Button-1>", lambda e, char=character: self.select_character(char))


    def create_thumbnail(self, image_path):
        """Create a thumbnail for the character list using CTkImage."""
        try:
            # Open the image
            img = Image.open(image_path)

            # Calculate the target aspect ratio
            target_aspect_ratio = 50 / 75

            # Get the image's current dimensions
            img_width, img_height = img.size
            img_aspect_ratio = img_width / img_height

            # Crop the image to the target aspect ratio
            if img_aspect_ratio > target_aspect_ratio:
                # Image is wider than target aspect ratio
                new_width = int(img_height * target_aspect_ratio)
                offset = (img_width - new_width) // 2
                img = img.crop((offset, 0, offset + new_width, img_height))
            elif img_aspect_ratio < target_aspect_ratio:
                # Image is taller than target aspect ratio
                new_height = int(img_width / target_aspect_ratio)
                offset = (img_height - new_height) // 2
                img = img.crop((0, offset, img_width, offset + new_height))

            # Resize to the target dimensions
            img = img.resize((50, 75), Image.Resampling.LANCZOS)

            # Return the resized image wrapped in a CTkImage
            return ctk.CTkImage(img, size=(50, 75))
        except Exception:
            # Use default thumbnail if image cannot be loaded
            default_img = Image.open("assets/default_thumbnail.png")
            return ctk.CTkImage(default_img, size=(50, 75))

    def create_edit_panel(self):
        """Create the right panel for editing character details."""
        # Create a scrollable frame for the entire edit panel
        self.edit_panel = ctk.CTkScrollableFrame(self)
        self.edit_panel.grid(row=0, column=2, sticky="nswe", padx=10, pady=10)

        # Message Banner
        self.message_banner = ctk.CTkLabel(
            self.edit_panel, text="", height=30, fg_color="#FFCDD2", corner_radius=5, text_color="black"
        )
        self.message_banner.pack(fill="x", padx=10, pady=5)
        self.message_banner.pack_forget()  # Hide initially

        # Title
        title_frame = ctk.CTkFrame(self.edit_panel, fg_color="transparent")
        title_frame.pack(fill="x", padx=10, pady=0)

        edit_label = ctk.CTkLabel(title_frame, text="Edit Character", font=ctk.CTkFont(size=18, weight="bold"))
        edit_label.pack(side="left")

        # Add Delete Button
        self.delete_button = ctk.CTkButton(
            title_frame,
            text="Delete",
            fg_color="red",
            hover_color="darkred",
            command=self.confirm_delete_character,
        )
        self.delete_button.pack(side="right", padx=5)

        # Character Name (label and input in the same row)
        name_frame = ctk.CTkFrame(self.edit_panel, fg_color="transparent")
        name_frame.pack(fill="x", padx=10, pady=0)

        self.name_label = ctk.CTkLabel(name_frame, text="Character Name:")
        self.name_label.pack(side="left", padx=0)

        self.name_entry = ctk.CTkEntry(name_frame)
        self.name_entry.pack(side="left", fill="x", expand=True, padx=5)

        # Create a CTkTabview for organizing sections
        tabview = ctk.CTkTabview(self.edit_panel, height=500)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Notes Tab
        notes_tab = tabview.add("Notes")
        self.notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
        self.notes_textbox.pack(fill="both", expand=True, padx=10, pady=5)

        self.misc_notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
        self.misc_notes_textbox.pack(fill="both", expand=True, padx=10, pady=5)

        # Extra Images Tab
        images_tab = tabview.add("Extra Images")
        self.extra_images_frame = ctk.CTkScrollableFrame(images_tab, height=200)
        self.extra_images_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.add_image_button = ctk.CTkButton(
            images_tab,
            text="Add Image",
            command=self.extra_images_manager.add_image_to_character
        )
        self.add_image_button.pack(pady=5, padx=10)

        # Metadata Tab
        metadata_tab = tabview.add("MetaData")
        self.main_file_label = ctk.CTkLabel(metadata_tab, text="Main File: ")
        self.main_file_label.pack(anchor="w", padx=10, pady=5)

        self.created_date_label = ctk.CTkLabel(metadata_tab, text="Created: ")
        self.created_date_label.pack(anchor="w", padx=10, pady=5)

        self.last_modified_date_label = ctk.CTkLabel(metadata_tab, text="Last Modified: ")
        self.last_modified_date_label.pack(anchor="w", padx=10, pady=5)

        # Save Button
        self.save_button = ctk.CTkButton(self.edit_panel, text="Save Changes", command=self.save_changes)
        self.save_button.pack(pady=10, padx=10, fill="x")


    def confirm_delete_character(self):
        """Show a confirmation prompt before deleting a character."""
        if not hasattr(self, "selected_character_id"):
            self.show_message("No character selected to delete.", "error")
            return

        # Confirmation dialog
        from tkinter.messagebox import askyesno

        confirm = askyesno(
            title="Delete Character",
            message="Are you sure you want to delete this character? This action cannot be undone.",
        )
        if confirm:
            self.delete_character()

    def delete_character(self):
        """Delete the selected character from the database and filesystem."""
        try:
            # Ensure we have a valid character ID
            if not hasattr(self, "selected_character_id"):
                raise ValueError("No character selected for deletion.")

            print(f"Deleting character ID: {self.selected_character_id}")

            # Get character folder name and main file from the database
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT name FROM characters WHERE id = ?",
                (self.selected_character_id,)
            )
            result = cursor.fetchone()
            connection.close()

            if not result:
                self.show_message("Character not found in the database.", "error")
                return

            character_name = result[0]
            folder_path = os.path.join("CharacterCards", character_name)

            # Remove folder if it exists
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
                print(f"Deleted folder: {folder_path}")
            else:
                print(f"Folder not found: {folder_path}")

            # Delete the record from the database
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()
            cursor.execute("DELETE FROM characters WHERE id = ?", (self.selected_character_id,))
            connection.commit()
            connection.close()

            # Remove the character from the UI list
            self.remove_character_from_list(self.selected_character_id)

            # Clear the edit panel (ensure widgets exist before clearing)
            if hasattr(self, "name_entry") and self.name_entry.winfo_exists():
                self.clear_edit_panel()

            # Show success message
            self.show_message("Character deleted successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to delete character: {str(e)}", "error")


    def remove_character_from_list(self, character_id):
        """Remove the character from the UI list."""
        try:
            for widget in self.scrollable_frame.winfo_children():
                if hasattr(widget, "character_id") and widget.character_id == character_id:
                    widget.destroy()
                    print(f"Removed character ID: {character_id} from UI.")
                    return
            print(f"Character ID: {character_id} not found in UI.")
        except Exception as e:
            print(f"Error removing character from list: {str(e)}")

    def clear_edit_panel(self):
        """Clear the edit panel fields."""
        self.name_entry.delete(0, "end")
        self.main_file_label.configure(text="Main File: ")
        self.notes_textbox.delete("1.0", "end")
        self.misc_notes_textbox.delete("1.0", "end")
        self.created_date_label.configure(text="Created: ")
        self.last_modified_date_label.configure(text="Last Modified: ")
        self.selected_character_id = None


    def add_character(self):
        """Open a new window to add a character."""
        # Create a modal window
        self.add_character_window = ctk.CTkToplevel(self)
        self.add_character_window.title("Add Character")
        self.add_character_window.geometry("400x400")

        # Ensure the modal stays on top of the main window
        self.add_character_window.transient(self)  # Set to be a child of the main window
        self.add_character_window.grab_set()       # Block interaction with the main window

        # Scrollable Frame for the Form
        scrollable_frame = ctk.CTkScrollableFrame(self.add_character_window, width=380, height=380)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Message Banner
        self.add_character_message_banner = ctk.CTkLabel(
            self.add_character_window, text="", height=30, fg_color="#FFCDD2", corner_radius=5, text_color="black"
        )
        self.add_character_message_banner.pack(fill="x", padx=10, pady=(5, 0))
        self.add_character_message_banner.pack_forget()  # Hide initially

        # File Upload Section
        file_frame = ctk.CTkFrame(scrollable_frame)  # Create a frame for the row
        file_frame.pack(fill="x", pady=10, padx=10, anchor="w")

        file_label = ctk.CTkLabel(file_frame, text="Upload File:", anchor="w")
        file_label.pack(side="left", padx=5)

        self.file_path_entry = ctk.CTkEntry(file_frame, placeholder_text="Select File", width=240)
        self.file_path_entry.pack(side="left", padx=5)

        browse_button = ctk.CTkButton(file_frame, text="Browse", width=100, command=self.browse_file)
        browse_button.pack(side="left", padx=5)

        # Character Name Section
        name_frame = ctk.CTkFrame(scrollable_frame)  # Create a frame for the row
        name_frame.pack(fill="x", pady=5, padx=10)

        name_label = ctk.CTkLabel(name_frame, text="Character Name:", anchor="w")
        name_label.pack(side="left", padx=5)

        self.character_name_entry = ctk.CTkEntry(name_frame, placeholder_text="Default: File Name", width=240)
        self.character_name_entry.pack(side="left", padx=5)

        # Character Notes
        notes_label = ctk.CTkLabel(scrollable_frame, text="Character Notes:", anchor="w")
        notes_label.pack(pady=10, padx=10, anchor="w")
        self.character_notes_textbox = ctk.CTkTextbox(scrollable_frame, height=100)
        self.character_notes_textbox.pack(pady=0, padx=10, fill="x")

        # Miscellaneous Notes
        misc_notes_label = ctk.CTkLabel(scrollable_frame, text="Miscellaneous Notes:", anchor="w")
        misc_notes_label.pack(pady=10, padx=10, anchor="w")
        self.misc_notes_textbox = ctk.CTkTextbox(scrollable_frame, height=100)
        self.misc_notes_textbox.pack(pady=0, padx=10, fill="x")

        # Submit Button
        submit_button = ctk.CTkButton(scrollable_frame, text="Add Character", command=self.save_character_with_message)
        submit_button.pack(pady=5, padx=10, anchor="w")

        # Center the modal on the screen
        self.add_character_window.update_idletasks()
        window_width = self.add_character_window.winfo_width()
        window_height = self.add_character_window.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        position_top = int((screen_height / 2) - (window_height / 2))
        position_right = int((screen_width / 2) - (window_width / 2))
        self.add_character_window.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")


    def show_add_character_message(self, message, message_type="error"):
        """Show a message in the Add Character window and hide it after 3 seconds."""
        if message_type == "success":
            self.add_character_message_banner.configure(fg_color="#C8E6C9", text_color="black")  # Green for success
        else:
            self.add_character_message_banner.configure(fg_color="#FFCDD2", text_color="black")  # Red for error

        self.add_character_message_banner.configure(text=message)
        self.add_character_message_banner.pack(fill="x", padx=10, pady=(5, 0))

        # Hide after 3 seconds
        self.add_character_window.after(3000, self.add_character_message_banner.pack_forget)


    def browse_file(self):
        """Open a file dialog to select an image or JSON file."""
        from tkinter.filedialog import askopenfilename
        file_path = askopenfilename(filetypes=[("Image/JSON Files", "*.png *.jpg *.jpeg *.json")])
        if file_path:
            self.file_path_entry.delete(0, "end")
            self.file_path_entry.insert(0, file_path)

            # Default character name to file name
            default_name = os.path.splitext(os.path.basename(file_path))[0]
            self.character_name_entry.delete(0, "end")
            self.character_name_entry.insert(0, default_name)

    def import_data(self):
        print("Import Data clicked")

    def export_data(self):
        print("Export Data clicked")

    def open_settings(self):
        print("Settings clicked")

    def select_character(self, character):
        """Handle character selection and populate the edit panel."""
        # Fetch all fields from the database for the selected character
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, name, main_file, notes, misc_notes, created_date, last_modified_date 
            FROM characters WHERE name = ?
            """,
            (character["name"],)
        )
        result = cursor.fetchone()
        connection.close()

        if result:
            # Store the ID of the selected character
            self.selected_character_id = result[0]  # Save the ID for later updates
            print(f"Selected character ID: {self.selected_character_id}")  # Debugging
            name, main_file, notes, misc_notes, created_date, last_modified_date = result[1:]

            # Ensure the misc_notes_textbox exists and can be updated
            if hasattr(self, 'misc_notes_textbox') and self.misc_notes_textbox.winfo_exists():
                self.misc_notes_textbox.delete("1.0", "end")
                self.misc_notes_textbox.insert("1.0", misc_notes)
            else:
                print("Error: misc_notes_textbox does not exist.")

            # Populate other fields in the edit panel
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, name)

            self.main_file_label.configure(text=f"Main File: {main_file}")
            self.notes_textbox.delete("1.0", "end")
            self.notes_textbox.insert("1.0", notes)
            self.created_date_label.configure(
                text=f"Created: {datetime.strptime(created_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}"
            )
            self.last_modified_date_label.configure(
                text=f"Last Modified: {datetime.strptime(last_modified_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}"
            )

            # Load extra images for the selected character
            self.load_extra_images()


    def save_changes(self):
        """Save changes made in the edit panel to the database."""
        # Fetch data from the edit panel
        character_name = self.name_entry.get().strip()
        main_file = self.main_file_label.cget("text").replace("Main File: ", "").strip()
        notes = self.notes_textbox.get("1.0", "end").strip()
        misc_notes = self.misc_notes_textbox.get("1.0", "end").strip()

        # Validate input
        if not character_name:
            self.show_message("Character name cannot be empty.", "error")
            return

        # Generate a new last_modified_date
        last_modified_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # Ensure we have a valid character ID
            if not hasattr(self, 'selected_character_id'):
                raise ValueError("No character selected for saving changes.")

            # Debugging: Print the ID being updated
            print(f"Updating character ID: {self.selected_character_id}")

            # Get old folder path from the database
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT name, main_file FROM characters WHERE id = ?",
                (self.selected_character_id,)
            )
            result = cursor.fetchone()
            connection.close()

            if not result:
                self.show_message("Original character data not found.", "error")
                return

            old_name, old_main_file = result
            old_folder_path = os.path.join("CharacterCards", old_name)
            new_folder_path = os.path.join("CharacterCards", character_name)

            # Update the folder name on the filesystem if the name changes
            if old_folder_path != new_folder_path:
                if os.path.exists(old_folder_path):
                    os.rename(old_folder_path, new_folder_path)
                else:
                    print(f"Folder not found: {old_folder_path}")
                    self.show_message("Folder not found. Unable to rename.", "error")
                    return

            # Update the database record
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()

            query = """
                UPDATE characters
                SET name = ?, notes = ?, misc_notes = ?, last_modified_date = ?
                WHERE id = ?
            """
            cursor.execute(
                query,
                (character_name, notes, misc_notes, last_modified_date, self.selected_character_id)
            )
            
            # Commit the transaction
            connection.commit()
            connection.close()

            # Check if any row was updated
            if cursor.rowcount == 0:
                self.show_message("No matching record found. Please check the character ID.", "error")
                return

            # Update the UI dynamically
            self.update_character_list(self.selected_character_id, character_name, last_modified_date)

            # Show success message
            self.show_message("Changes saved successfully.", "success")
        except Exception as e:
            self.show_message(f"Failed to save changes: {str(e)}", "error")

    def select_character_by_id(self, character_id):
        """Handle character selection by ID and populate the edit panel."""
        # Fetch all fields from the database for the selected character
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, name, main_file, notes, misc_notes, created_date, last_modified_date 
            FROM characters WHERE id = ?
            """,
            (character_id,),
        )
        result = cursor.fetchone()
        connection.close()

        if result:
            # Store the ID of the selected character
            self.selected_character_id = result[0]  # Save the ID for later updates
            name, main_file, notes, misc_notes, created_date, last_modified_date = result[1:]

            # Populate the fields in the edit panel
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, name)

            self.main_file_label.configure(text=f"Main File: {main_file}")
            self.notes_textbox.delete("1.0", "end")
            self.notes_textbox.insert("1.0", notes)
            self.misc_notes_textbox.delete("1.0", "end")
            self.misc_notes_textbox.insert("1.0", misc_notes)
            self.created_date_label.configure(
                text=f"Created: {datetime.strptime(created_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}"
            )
            self.last_modified_date_label.configure(
                text=f"Last Modified: {datetime.strptime(last_modified_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}"
            )

            # Load extra images for the selected character
            self.load_extra_images()


    def update_character_list(self, character_id, character_name, last_modified_date):
        """Update the character list dynamically after changes."""
        formatted_date = datetime.strptime(last_modified_date, "%Y-%m-%d %H:%M:%S").strftime("%m/%d/%Y %I:%M %p")

        # Find the character frame and update it
        for widget in self.scrollable_frame.winfo_children():
            # Check if the widget has a `character_id` attribute
            if hasattr(widget, "character_id") and widget.character_id == character_id:
                # Update the name and last modified date
                for sub_widget in widget.winfo_children():
                    if isinstance(sub_widget, ctk.CTkLabel):
                        if sub_widget.cget("text").startswith("Last Modified:"):
                            sub_widget.configure(text=f"Last Modified: {formatted_date}")
                        elif sub_widget.cget("text") == widget.character_name:
                            sub_widget.configure(text=character_name)

                # Update internal attributes for consistency
                widget.character_name = character_name

                # Rebind click events for the updated frame and its children, including the image
                for sub_widget in widget.winfo_children():
                    sub_widget.bind(
                        "<Button-1>",
                        lambda e, char_id=character_id: self.select_character_by_id(char_id),
                    )
                widget.bind(
                    "<Button-1>",
                    lambda e, char_id=character_id: self.select_character_by_id(char_id),
                )

                return

    def save_character_with_message(self):
        """Save the character to the database and filesystem, with messages."""
        file_path = self.file_path_entry.get()
        character_name = self.character_name_entry.get().strip()
        character_notes = self.character_notes_textbox.get("1.0", "end").strip()
        misc_notes = self.misc_notes_textbox.get("1.0", "end").strip()

        # Validate input
        if not file_path:
            self.show_add_character_message("Please select a file.", "error")
            return
        if not character_name:
            self.show_add_character_message("Please provide a character name.", "error")
            return

        # Check for duplicate character name
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM characters WHERE name = ?", (character_name,))
        if cursor.fetchone()[0] > 0:
            self.show_add_character_message("Character name already exists. Please choose another name.", "error")
            connection.close()
            return

        # Save file to directory
        character_dir = os.path.join("CharacterCards", character_name)
        os.makedirs(character_dir, exist_ok=True)
        try:
            shutil.copy(file_path, character_dir)
        except Exception as e:
            self.show_add_character_message(f"File save error: {str(e)}", "error")
            return

        # Generate timestamps
        created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_modified_date = created_date

        # Add to database
        try:
            cursor.execute(
                """INSERT INTO characters 
                (name, main_file, notes, misc_notes, created_date, last_modified_date) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (character_name, os.path.basename(file_path), character_notes, misc_notes, created_date, last_modified_date),
            )
            connection.commit()
            connection.close()
        except Exception as e:
            self.show_add_character_message(f"Database error: {str(e)}", "error")
            return

        # Immediately update the character list
        self.add_character_to_list({
            "id": cursor.lastrowid,
            "name": character_name,
            "image_path": os.path.join(character_dir, os.path.basename(file_path)),
            "created_date": created_date,
            "last_modified_date": last_modified_date,
        })

        # Show success message and close the modal after a short delay
        self.show_add_character_message("Character added successfully.", "success")
        self.add_character_window.after(1500, self.add_character_window.destroy)



    def show_message(self, message, message_type="error"):
        """Show a message in the banner and hide it after 3 seconds."""
        if message_type == "success":
            self.message_banner.configure(fg_color="#C8E6C9", text_color="black")  # Green for success
        else:
            self.message_banner.configure(fg_color="#FFCDD2", text_color="black")  # Red for error

        self.message_banner.configure(text=message)
        self.message_banner.pack(fill="x", padx=10, pady=5)

        # Hide after 3 seconds
        self.after(3000, self.message_banner.pack_forget)


    def get_character_name(self):
        """Retrieve the character's name using the selected character ID."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM characters WHERE id = ?", (self.selected_character_id,))
        result = cursor.fetchone()
        connection.close()
        return result[0] if result else "Unknown"
    

if __name__ == "__main__":
    app = CharacterCardManagerApp()
    app.mainloop()
