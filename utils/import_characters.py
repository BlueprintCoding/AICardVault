import os
import shutil
from PIL import Image, ImageTk
import customtkinter as ctk
from tkinter import messagebox
import threading


class ImportModal:
    def __init__(self, parent, db_manager, sillytavern_path, refresh_callback):
        self.parent = parent
        self.db_manager = db_manager
        self.sillytavern_path = sillytavern_path
        self.refresh_callback = refresh_callback  # Callback to refresh the character list
        self.modal = None
        self.checkbuttons = {}
        self.toggle_state = True
        self.character_count = 0
        self.selected_count = 0


    def open(self):
        # Create the modal window
        self.modal = ctk.CTkToplevel(self.parent)
        self.modal.title("Import Characters")
        self.modal.geometry("700x700")  # Adjusted for layout changes

        # Ensure the modal stays on top of the main window
        self.modal.transient(self.parent)
        self.modal.grab_set()

        # Loading label
        self.loading_label = ctk.CTkLabel(
            self.modal,
            text="Loading Characters, please wait...\nIf you have a lot of character cards, this may take a second.",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="center",
        )
        self.loading_label.pack(pady=20, padx=10)

        # Create a scrollable frame for character list
        self.scrollable_frame = ctk.CTkScrollableFrame(self.modal, width=680, height=580)
        self.scrollable_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Button frame for Check All/Uncheck All, Import, and Cancel
        button_frame = ctk.CTkFrame(self.modal)
        button_frame.pack(pady=10, padx=10, fill="x")

        # Check All/Uncheck All Button
        self.toggle_button = ctk.CTkButton(
            button_frame,
            text="Uncheck All",
            command=self.toggle_checkboxes,
            width=100,
        )
        self.toggle_button.pack(side="left", padx=5, pady=5)

        # Character Count Label
        self.count_label = ctk.CTkLabel(
            button_frame,
            text="0/0",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.count_label.pack(side="left", padx=5)

        # Import Button
        import_button = ctk.CTkButton(
            button_frame,
            text="Import",
            command=self.import_characters,
            width=100,
        )
        import_button.pack(side="right", padx=5, pady=5)

        # Cancel Button
        cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.modal.destroy,
            width=100,
        )
        cancel_button.pack(side="right", padx=5, pady=5)

        # Start loading characters in a separate thread
        threading.Thread(target=self.load_characters, daemon=True).start()

    def load_characters(self):
        """Load all character thumbnails and widgets, then update the GUI."""
        characters_path = os.path.join(self.sillytavern_path, "characters")
        if not os.path.exists(characters_path):
            messagebox.showerror("Error", f"Path not found: {characters_path}")
            self.modal.destroy()
            return

        png_files = [f for f in os.listdir(characters_path) if f.endswith(".png")]
        self.character_count = len(png_files)
        self.selected_count = self.character_count  # All are selected by default

        if not png_files:
            messagebox.showinfo("No Characters", "No PNG files found in the specified folder.")
            self.modal.destroy()
            return

        # Prepare widgets for all PNG files
        widgets = []
        for png_file in png_files:
            widget = self.create_character_widget(png_file, characters_path)
            widgets.append(widget)

        # Add all widgets to the GUI at once
        self.modal.after(0, lambda: self.add_widgets_to_frame(widgets))

    def create_character_widget(self, png_file, characters_path):
        """Create a frame widget for a character."""
        frame = ctk.CTkFrame(self.scrollable_frame)

        # Checkbox for selecting character
        checkbox_var = ctk.BooleanVar(value=True)  # Checked by default
        checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            variable=checkbox_var,
            width=20,
            command=lambda: self.update_count(checkbox_var.get()),
        )
        checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.checkbuttons[png_file] = {"checked": checkbox_var}

        # Character Name Input
        character_name = os.path.splitext(png_file)[0]
        entry = ctk.CTkEntry(frame, placeholder_text="Enter character name", width=350)
        entry.insert(0, character_name)  # Default to file name without .png
        entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        self.checkbuttons[png_file]["entry"] = entry

        # Thumbnail
        image_path = os.path.join(characters_path, png_file)
        thumbnail = self.create_thumbnail(image_path)
        thumbnail_label = ctk.CTkLabel(frame, image=thumbnail, text="")
        thumbnail_label.image = thumbnail  # Keep a reference to avoid garbage collection
        thumbnail_label.grid(row=0, column=2, padx=5, pady=5, sticky="e")

        frame.grid_columnconfigure(1, weight=1)  # Make the entry field fill available space

        return frame

    def add_widgets_to_frame(self, widgets):
        """Add prepared widgets to the scrollable frame."""
        for widget in widgets:
            widget.pack(fill="x", padx=5, pady=5)

        # Update count label and remove loading label after updating the GUI
        self.update_count_label()
        self.loading_label.destroy()

    def update_count(self, is_checked):
        """Update the selected character count based on checkbox state."""
        self.selected_count += 1 if is_checked else -1
        self.update_count_label()

    def update_count_label(self):
        """Update the character count label text."""
        self.count_label.configure(text=f"{self.selected_count}/{self.character_count}")

    def toggle_checkboxes(self):
        """Toggle all checkboxes between checked and unchecked."""
        self.toggle_state = not self.toggle_state
        for data in self.checkbuttons.values():
            data["checked"].set(self.toggle_state)
        self.selected_count = self.character_count if self.toggle_state else 0
        button_text = "Uncheck All" if self.toggle_state else "Check All"
        self.toggle_button.configure(text=button_text)
        self.update_count_label()

    def import_characters(self):
        """Import selected characters into the application."""
        characters_path = os.path.join(self.sillytavern_path, "characters")
        app_characters_path = os.path.join("CharacterCards")

        if not os.path.exists(app_characters_path):
            os.makedirs(app_characters_path)

        imported_count = 0
        for png_file, data in self.checkbuttons.items():
            if data["checked"].get():
                # Get character name
                character_name = data["entry"].get().strip() or os.path.splitext(png_file)[0]
                character_folder = os.path.join(app_characters_path, character_name)
                if not os.path.exists(character_folder):
                    os.makedirs(character_folder)

                # Copy PNG file to app character folder
                src = os.path.join(characters_path, png_file)
                dest = os.path.join(character_folder, png_file)
                shutil.copy(src, dest)

                # Add to database
                self.db_manager.add_character_to_db(character_name, png_file)
                imported_count += 1

        messagebox.showinfo("Import Complete", f"{imported_count} characters have been imported successfully.")
        self.modal.destroy()

        # Refresh the character list in the main application
        if self.refresh_callback:
            self.refresh_callback()


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