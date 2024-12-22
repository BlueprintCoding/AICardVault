import customtkinter as ctk
from PIL import Image, ImageTk
import os
import re 
import shutil
import sqlite3
import time
from functools import partial
from utils.db_manager import DatabaseManager
from utils.file_handler import FileHandler
from datetime import datetime
from utils.extra_images import ExtraImagesManager
from utils.settings import SettingsModal
from utils.import_characters import ImportModal
from utils.aicc_site_functions import AICCImporter

class CharacterCardManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Card Vault")
        self.geometry("1400x700")
        ctk.set_appearance_mode("dark")  # Use system theme
        ctk.set_default_color_theme("assets/AiCardVaultTheme.json")
        self.current_page = 0  # Start at the first page
        self.items_per_page = 6  # Display 8 cards per page
        self.total_pages = 0  # Calculate based on the number of items
        self.filtered_characters = []  # This will hold the search results
        self.search_debounce_timer = None

        # Initialize database and file handler
        self.db_manager = DatabaseManager()
        self.file_handler = FileHandler()

          # Load settings from the database
        self.settings = {
            "appearance_mode": self.db_manager.get_setting("appearance_mode", "dark"),
            "sillytavern_path": self.db_manager.get_setting("sillytavern_path", ""),
        }


        # Ensure default sort order is set if not already present
        if not self.db_manager.get_setting("default_sort_order"):
            self.db_manager.set_setting("default_sort_order", "A - Z")

        # Apply appearance mode
        ctk.set_appearance_mode(self.settings["appearance_mode"])
        
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

    def open_settings(self):
        """Open the settings modal."""
        settings_modal = SettingsModal(
            parent=self,
            db_manager=self.db_manager,
            update_settings_callback=self.update_settings,
        )
        settings_modal.open()

    def update_settings(self, updated_settings):
        """Callback to update settings in the main application."""
        self.settings.update(updated_settings)

        # Persist settings in the database
        self.db_manager.set_setting("appearance_mode", updated_settings["appearance_mode"])
        self.db_manager.set_setting("sillytavern_path", updated_settings["sillytavern_path"])
        self.db_manager.set_setting("default_sort_order", updated_settings["default_sort_order"])

        # Apply appearance mode
        ctk.set_appearance_mode(updated_settings["appearance_mode"])

        # Refresh sort order in the character list
        self.sort_var.set(updated_settings["default_sort_order"])
        self.sort_character_list(updated_settings["default_sort_order"])

        print("Settings updated:", updated_settings)

    def open_import_modal(self):
        sillytavern_path = self.db_manager.get_setting("sillytavern_path", "")
        if not sillytavern_path:
            self.show_message("SillyTavern path not configured. Set it in Settings.", "error")
            return

        def refresh_character_list():
            self.scrollable_frame.destroy()  # Destroy the old frame
            self.create_character_list()    # Recreate the character list

        import_modal = ImportModal(self, self.db_manager, sillytavern_path, refresh_character_list)
        import_modal.open()

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

        # Space for "Currently Selected Character"
        self.selected_character_frame = None  # Will be created when a character is selected

        # Buttons in the sidebar
        self.add_character_button = ctk.CTkButton(self.sidebar, text="Add Character", command=self.add_character)
        self.add_character_button.pack(pady=10, padx=10, fill="x")

        self.import_button = ctk.CTkButton(self.sidebar, text="Import Cards From SillyTavern", command=self.open_import_modal)
        self.import_button.pack(pady=10, padx=10, fill="x")

        # self.export_button = ctk.CTkButton(self.sidebar, text="Export Data", command=self.export_data)
        # self.export_button.pack(pady=10, padx=10, fill="x")

        self.settings_button = ctk.CTkButton(self.sidebar, text="Settings", command=self.open_settings)
        self.settings_button.pack(pady=10, padx=10, fill="x")

    def create_character_list(self):
        """Create the middle column for the character list."""
        self.character_list_frame = ctk.CTkFrame(self)
        self.character_list_frame.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)

        # Title
        list_label = ctk.CTkLabel(self.character_list_frame, text="Character List", font=ctk.CTkFont(size=14, weight="bold"))
        list_label.pack(pady=(10, 0))

        # Search Bar
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            self.character_list_frame,
            textvariable=self.search_var,
            placeholder_text="Search characters...",
            width=300,
        )
        search_entry.pack(pady=(10, 5), padx=10)

        # Bind the search entry to the debounce function
        self.search_var.trace_add("write", lambda *args: self.debounce_search())

            # Character Tags Filter Button
        self.character_tags_filter = []
        char_tags_button = ctk.CTkButton(
            self.character_list_frame,
            text="Filter by Character Tags",
            command=lambda: self.open_tag_filter_modal("Character Tags", "character", self.character_tags_filter),
        )
        char_tags_button.pack(pady=5, padx=10)

        # Model/API Tags Filter Button
        self.model_api_tags_filter = []
        model_tags_button = ctk.CTkButton(
            self.character_list_frame,
            text="Filter by Model/API Tags",
            command=lambda: self.open_tag_filter_modal("Model/API Tags", "model_api", self.model_api_tags_filter),
        )
        model_tags_button.pack(pady=5, padx=10)

        # Scrollable Frame for Characters
        self.scrollable_frame = ctk.CTkScrollableFrame(self.character_list_frame)
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Navigation Buttons
        self.create_navigation_buttons()

                # Sort Dropdown
        default_sort_order = self.db_manager.get_setting("default_sort_order", "A - Z")
        self.sort_var = ctk.StringVar(value=default_sort_order)
        sort_dropdown = ctk.CTkOptionMenu(
            self.character_list_frame,
            values=["A - Z", "Z - A", "Newest", "Oldest", "Most Recently Edited"],
            variable=self.sort_var,
            command=self.sort_character_list
        )
        sort_dropdown.pack(pady=(5, 10), padx=10)

        # Initialize Card Count Label early
        self.card_count_label = ctk.CTkLabel(
            self.character_list_frame,
            text="Total Cards: 0",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.card_count_label.pack(pady=(0, 5))

        # Load and display all characters initially
        self.all_characters = self.get_character_list()

        # Default Sort
        
        self.filtered_characters = self.all_characters.copy()  # Initially, no filtering
        self.sort_character_list(default_sort_order)

        # Display characters
        self.display_characters()

    def open_tag_filter_modal(self, title, category, filter_list):
        """Open a multi-select modal for tag filtering."""
        tags = self.get_all_tags(category)
        MultiSelectModal(
            self,
            title,
            tags,
            filter_list,
            callback=lambda selected: self.apply_tag_filter(category, selected),
        )

    def apply_tag_filter(self, category, selected):
        """Apply the selected tags as filters."""
        if category == "character":
            self.character_tags_filter = selected
        elif category == "model_api":
            self.model_api_tags_filter = selected
        self.filter_character_list()

    def get_all_tags(self, category):
        """Fetch all unique tags for the given category."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT name FROM tags WHERE category = ?", (category,))
        tags = [row[0] for row in cursor.fetchall()]
        connection.close()
        return tags

    def character_has_tags(self, character_id, tags, category):
        """Check if a character has all the selected tags."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT t.name FROM tags t
            JOIN character_tags ct ON t.id = ct.tag_id
            WHERE ct.character_id = ? AND t.category = ?
        """, (character_id, category))
        character_tags = {row[0] for row in cursor.fetchall()}
        connection.close()
        return all(tag in character_tags for tag in tags)


    def sort_character_list(self, sort_option):
        """Sort the character list based on the selected option."""
        # Sort logic
        if sort_option == "A - Z":
            self.filtered_characters.sort(key=lambda char: char["name"].lower())
        elif sort_option == "Z - A":
            self.filtered_characters.sort(key=lambda char: char["name"].lower(), reverse=True)
        elif sort_option == "Newest":
            self.filtered_characters.sort(key=lambda char: char["created_date"], reverse=True)
        elif sort_option == "Oldest":
            self.filtered_characters.sort(key=lambda char: char["created_date"])
        elif sort_option == "Most Recently Edited":
            self.filtered_characters.sort(key=lambda char: char["last_modified_date"], reverse=True)

        # Recalculate pages and refresh the display
        self.total_pages = (len(self.filtered_characters) + self.items_per_page - 1) // self.items_per_page
        self.current_page = 0  # Reset to the first page
        self.display_characters()
        self.update_navigation_buttons()



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
        char_frame = ctk.CTkFrame(self.scrollable_frame, corner_radius=5, border_width=0, border_color="")
        char_frame.character_id = character["id"]  # Assign the character ID
        char_frame.character_name = character["name"]  # Assign the character name
        char_frame.pack(pady=5, padx=5, fill="x")

        image_path = character.get("image_path", "assets/default_thumbnail.png")
        created_date = character.get("created_date", "Unknown Date")
        last_modified_date = character.get("last_modified_date", "Unknown Date")

        # Reformat dates for display
        formatted_created_date = self.format_date(created_date)
        formatted_last_modified_date = self.format_date(last_modified_date)

        # Layout for character frame
        char_frame.grid_columnconfigure(0, weight=0)  # Fixed size for image column
        char_frame.grid_columnconfigure(1, weight=1)  # Flexible size for text column

        # Add Thumbnail
        thumbnail = self.create_thumbnail(image_path)
        thumbnail_label = ctk.CTkLabel(char_frame, image=thumbnail, text="")
        thumbnail_label.image = thumbnail
        thumbnail_label.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky="n")

        # Character Name Label
        name_label = ctk.CTkLabel(char_frame, text=character["name"], anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        name_label.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        # Created Date Label
        created_date_label = ctk.CTkLabel(char_frame, text=f"Created: {formatted_created_date}", anchor="w", font=ctk.CTkFont(size=12))
        created_date_label.grid(row=1, column=1, sticky="w", padx=5)

        # Last Modified Date Label
        modified_date_label = ctk.CTkLabel(char_frame, text=f"Last Modified: {formatted_last_modified_date}", anchor="w", font=ctk.CTkFont(size=12))
        modified_date_label.grid(row=2, column=1, sticky="w", pady=(0,3), padx=5)

        # Bind click events to `select_character_by_id`
        widgets_to_bind = [char_frame, thumbnail_label, name_label, created_date_label, modified_date_label]
        for widget in widgets_to_bind:
            widget.bind("<Button-1>", lambda e, char_id=character["id"]: self.select_character_by_id(char_id))

        # Update card count
        self.card_count_label.configure(text=f"Total Cards: {len(self.all_characters)}")
        
    def filter_character_list(self):
        """Filter the character list based on search query and selected tags."""
        query = self.search_var.get().lower().strip()
        selected_character_tags = self.character_tags_filter
        selected_model_api_tags = self.model_api_tags_filter

        self.filtered_characters = [
            char for char in self.all_characters
            if (not query or query in char["name"].lower())
            and (not selected_character_tags or self.character_has_tags(char["id"], selected_character_tags, "character"))
            and (not selected_model_api_tags or self.character_has_tags(char["id"], selected_model_api_tags, "model_api"))
        ]

        # Recalculate pages and refresh the display
        self.total_pages = (len(self.filtered_characters) + self.items_per_page - 1) // self.items_per_page
        self.current_page = 0
        self.display_characters()
        self.update_navigation_buttons()



    def debounce_search(self, *args):
        """Debounce the search input to prevent rapid calls."""
        # Cancel the existing timer if there is one
        if self.search_debounce_timer is not None:
            self.after_cancel(self.search_debounce_timer)

        # Set a new timer to execute the actual search function
        self.search_debounce_timer = self.after(300, self.filter_character_list)
            
    def display_characters(self):
        """Display the characters for the current page."""
        # Clear the current list
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Calculate start and end indices for the current page
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page

        # Get the characters for the current page
        characters_to_display = self.filtered_characters[start_index:end_index]

        # Add characters to the list
        for char in characters_to_display:
            self.add_character_to_list(char)

        # Update the card count label
        self.card_count_label.configure(
            text=f"Showing {len(self.filtered_characters)} Results | Page {self.current_page + 1} of {self.total_pages}"
        )


    def create_navigation_buttons(self):
        """Create navigation buttons for pagination with a page number box."""
        nav_frame = ctk.CTkFrame(self.character_list_frame)
        nav_frame.pack(fill="x", pady=(5, 10))

        # Previous Button
        self.prev_button = ctk.CTkButton(nav_frame, text="Previous", command=self.prev_page)
        self.prev_button.pack(side="left", padx=5)

        # Page Number Entry
        self.page_var = ctk.StringVar(value="1")
        self.page_entry = ctk.CTkEntry(
            nav_frame,
            textvariable=self.page_var,
            width=50,
            justify="center"
        )
        self.page_entry.pack(side="left", padx=5)
        self.page_entry.bind("<Return>", lambda e: self.jump_to_page())  # Trigger jump on Enter key

        # Total Pages Label
        self.total_pages_label = ctk.CTkLabel(
            nav_frame,
            text=f"of {self.total_pages}",
            font=ctk.CTkFont(size=12),
            text_color="gray"  # Corrected: Set text_color directly on the label
        )
        self.total_pages_label.pack(side="left", padx=5)

        # Next Button
        self.next_button = ctk.CTkButton(nav_frame, text="Next", command=self.next_page)
        self.next_button.pack(side="right", padx=5)

        self.update_navigation_buttons()
        
    def jump_to_page(self):
        """Jump to a specific page entered in the page number box."""
        try:
            page_number = int(self.page_var.get()) - 1  # Convert to zero-based index
            if 0 <= page_number < self.total_pages:
                self.current_page = page_number
                self.display_characters()
                self.update_navigation_buttons()
            else:
                self.show_message("Invalid page number.", "error")
        except ValueError:
            self.show_message("Please enter a valid number.", "error")

    def update_navigation_buttons(self):
        """Enable or disable navigation buttons based on the current page and update page number."""
        self.prev_button.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_page < self.total_pages - 1 else "disabled")

        # Update page number and total pages label
        self.page_var.set(str(self.current_page + 1))
        self.total_pages_label.configure(text=f"of {self.total_pages}")

    def prev_page(self):
        """Go to the previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_characters()
            self.update_navigation_buttons()

    def next_page(self):
        """Go to the next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_characters()
            self.update_navigation_buttons()


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
        self.edit_panel.grid(row=0, column=2, sticky="nswe", padx=(10,20), pady=10)

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
            fg_color="#f37a21",
            hover_color="#bc5c14",
            width=50,
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
            # Notes Section
        self.notes_label = ctk.CTkLabel(notes_tab, text="Character Notes:", font=ctk.CTkFont(size=14, weight="bold"))
        self.notes_label.pack(pady=(10, 5), padx=0, anchor="w")

        self.notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
        self.notes_textbox.pack(fill="both", expand=True, padx=0, pady=5)

        self.misc_notes_label = ctk.CTkLabel(notes_tab, text="Miscellaneous Notes:", font=ctk.CTkFont(size=14, weight="bold"))
        self.misc_notes_label.pack(pady=(10, 5), padx=5, anchor="w")

        self.misc_notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
        self.misc_notes_textbox.pack(fill="both", expand=True, padx=0, pady=5)

        # Extra Images Tab
        images_tab = tabview.add("Images")
        self.extra_images_frame = ctk.CTkScrollableFrame(images_tab, height=200)
        self.extra_images_frame.pack(fill="both", expand=True, padx=0, pady=5)

        self.add_image_button = ctk.CTkButton(
            images_tab,
            text="Add Image",
            command=self.extra_images_manager.add_image_to_character
        )
        self.add_image_button.pack(pady=5, padx=10)

        # Related Characters Tab
        related_tab = tabview.add("Related")

        # Search Bar for Related Characters
        self.related_search_var = ctk.StringVar()
        related_search_entry = ctk.CTkEntry(
            related_tab,
            textvariable=self.related_search_var,
            placeholder_text="Search characters...",
            width=300,
        )
        related_search_entry.pack(pady=(10, 5), padx=10)

        # Bind search bar to filter function
        self.related_search_var.trace_add("write", lambda *args: self.filter_related_characters())

        # Scrollable Frame for Related Characters List
        self.related_characters_frame = ctk.CTkScrollableFrame(related_tab, height=200)
        self.related_characters_frame.pack(fill="both", expand=True, padx=0, pady=5)

        # Add Button for Linking a Character
        self.add_related_character_button = ctk.CTkButton(
            related_tab,
            text="Link Character",
            command=self.open_link_character_modal
        )
        self.add_related_character_button.pack(pady=5, padx=10)
                
        # Tags Tab
        tags_tab = tabview.add("Tags")

        # Character Tags Section
        character_tag_label = ctk.CTkLabel(tags_tab, text="Assigned Character Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        character_tag_label.pack(pady=(2, 1), padx=5, anchor="w")

        # Wrapping frame for assigned character tags
        assigned_character_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        assigned_character_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        assigned_character_frame_wrapper.pack_propagate(False)

        # Assigned Tags Frame inside wrapper
        self.assigned_character_tags_frame = ctk.CTkScrollableFrame(assigned_character_frame_wrapper)
        self.assigned_character_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Potential Tags Frame
        all_character_tag_label = ctk.CTkLabel(tags_tab, text="Available Character Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        all_character_tag_label.pack(pady=(2, 1), padx=5, anchor="w")

        # Wrapping frame for potential character tags
        potential_character_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        potential_character_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        potential_character_frame_wrapper.pack_propagate(False)

        # Potential Tags Frame inside wrapper
        self.potential_character_tags_frame = ctk.CTkScrollableFrame(potential_character_frame_wrapper)
        self.potential_character_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Search/Add Input for Character Tags
        self.character_tag_search_var = ctk.StringVar()
        character_tag_frame = ctk.CTkFrame(tags_tab, fg_color="transparent")
        character_tag_frame.pack(fill="x", padx=10, pady=(1, 2))

        character_tag_entry = ctk.CTkEntry(
            character_tag_frame,
            textvariable=self.character_tag_search_var,
            placeholder_text="Search or add character tags...",
            width=260,
        )
        character_tag_entry.pack(side="left", fill="x", expand=True)

        # Bind search entry events
        character_tag_entry.bind("<KeyRelease>", lambda e: self.update_tag_search_results(
            self.character_tag_search_var.get(), "character", self.potential_character_tags_frame
        ))
        character_tag_entry.bind("<Return>", lambda e: self.add_tag(self.character_tag_search_var.get(), "character"))

        # Add Tag Button
        character_add_tag_button = ctk.CTkButton(
            character_tag_frame,
            text="+",
            width=30,
            command=lambda: self.add_tag_from_input(self.character_tag_search_var, "character")
        )
        character_add_tag_button.pack(side="left", padx=(5, 0))

        # Load all potential character tags by default
        self.update_tag_search_results("", "character", self.potential_character_tags_frame)

        # Model/API Tags Section
        model_api_tag_label = ctk.CTkLabel(tags_tab, text="Assigned Model/API Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        model_api_tag_label.pack(pady=2, padx=5, anchor="w")

        # Wrapping frame for assigned model/API tags
        assigned_model_api_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        assigned_model_api_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        assigned_model_api_frame_wrapper.pack_propagate(False)

        # Assigned Tags Frame inside wrapper
        self.assigned_model_api_tags_frame = ctk.CTkScrollableFrame(assigned_model_api_frame_wrapper)
        self.assigned_model_api_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Model/API Tags Section
        all_model_api_tag_label = ctk.CTkLabel(tags_tab, text="Available Model/API Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        all_model_api_tag_label.pack(pady=2, padx=5, anchor="w")

        # Wrapping frame for potential model/API tags
        potential_model_api_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        potential_model_api_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        potential_model_api_frame_wrapper.pack_propagate(False)

        # Potential Tags Frame inside wrapper
        self.potential_model_api_tags_frame = ctk.CTkScrollableFrame(potential_model_api_frame_wrapper)
        self.potential_model_api_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Search/Add Input for Model/API Tags
        self.model_api_tag_search_var = ctk.StringVar()
        model_api_tag_frame = ctk.CTkFrame(tags_tab, fg_color="transparent")
        model_api_tag_frame.pack(fill="x", padx=0, pady=(1, 1))

        model_api_tag_entry = ctk.CTkEntry(
            model_api_tag_frame,
            textvariable=self.model_api_tag_search_var,
            placeholder_text="Search or add model/api tags...",
            placeholder_text_color="#ffffff",
            width=260,
        )
        model_api_tag_entry.pack(side="left", fill="x", expand=True)

        # Bind search entry events
        model_api_tag_entry.bind("<KeyRelease>", lambda e: self.update_tag_search_results(
            self.model_api_tag_search_var.get(), "model_api", self.potential_model_api_tags_frame
        ))
        model_api_tag_entry.bind("<Return>", lambda e: self.add_tag(self.model_api_tag_search_var.get(), "model_api"))

        # Add Tag Button
        model_api_add_tag_button = ctk.CTkButton(
            model_api_tag_frame,
            text="+",
            width=30,
            command=lambda: self.add_tag_from_input(self.model_api_tag_search_var, "model_api")
        )
        model_api_add_tag_button.pack(side="left", padx=(5, 0))

        # Load all potential model/API tags by default
        self.update_tag_search_results("", "model_api", self.potential_model_api_tags_frame)


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

        # Bind mouse wheel scrolling for main scrollable frames
        self.bind_mouse_wheel(self.scrollable_frame)  # Character list
        self.bind_mouse_wheel(self.edit_panel)  # Edit panel
        self.bind_mouse_wheel(self.extra_images_frame)  # Extra Images

        # Related Characters
        self.bind_mouse_wheel(self.related_characters_frame)

        # Tags
        self.bind_mouse_wheel(self.assigned_character_tags_frame)
        self.bind_mouse_wheel(self.potential_character_tags_frame)
        self.bind_mouse_wheel(self.assigned_model_api_tags_frame)
        self.bind_mouse_wheel(self.potential_model_api_tags_frame)

    def create_edit_panel(self):
        """Create the right panel for editing character details."""
        # Create a scrollable frame for the entire edit panel
        self.edit_panel = ctk.CTkScrollableFrame(self)
        self.edit_panel.grid(row=0, column=2, sticky="nswe", padx=(10,20), pady=10)

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
            fg_color="#f37a21",
            hover_color="#bc5c14",
            width=50,
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
            # Notes Section
        self.notes_label = ctk.CTkLabel(notes_tab, text="Character Notes:", font=ctk.CTkFont(size=14, weight="bold"))
        self.notes_label.pack(pady=(10, 5), padx=0, anchor="w")

        self.notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
        self.notes_textbox.pack(fill="both", expand=True, padx=0, pady=5)

        self.misc_notes_label = ctk.CTkLabel(notes_tab, text="Miscellaneous Notes:", font=ctk.CTkFont(size=14, weight="bold"))
        self.misc_notes_label.pack(pady=(10, 5), padx=5, anchor="w")

        self.misc_notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
        self.misc_notes_textbox.pack(fill="both", expand=True, padx=0, pady=5)

        # Extra Images Tab
        images_tab = tabview.add("Images")
        self.extra_images_frame = ctk.CTkScrollableFrame(images_tab, height=200)
        self.extra_images_frame.pack(fill="both", expand=True, padx=0, pady=5)

        self.add_image_button = ctk.CTkButton(
            images_tab,
            text="Add Image",
            command=self.extra_images_manager.add_image_to_character
        )
        self.add_image_button.pack(pady=5, padx=10)

        # Related Characters Tab
        related_tab = tabview.add("Related")

        # Search Bar for Related Characters
        self.related_search_var = ctk.StringVar()
        related_search_entry = ctk.CTkEntry(
            related_tab,
            textvariable=self.related_search_var,
            placeholder_text="Search characters...",
            width=300,
        )
        related_search_entry.pack(pady=(10, 5), padx=10)

        # Bind search bar to filter function
        self.related_search_var.trace_add("write", lambda *args: self.filter_related_characters())

        # Scrollable Frame for Related Characters List
        self.related_characters_frame = ctk.CTkScrollableFrame(related_tab, height=200)
        self.related_characters_frame.pack(fill="both", expand=True, padx=0, pady=5)

        # Add Button for Linking a Character
        self.add_related_character_button = ctk.CTkButton(
            related_tab,
            text="Link Character",
            command=self.open_link_character_modal
        )
        self.add_related_character_button.pack(pady=5, padx=10)
                
        # Tags Tab
        tags_tab = tabview.add("Tags")

        # Character Tags Section
        character_tag_label = ctk.CTkLabel(tags_tab, text="Assigned Character Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        character_tag_label.pack(pady=(2, 1), padx=5, anchor="w")

        # Wrapping frame for assigned character tags
        assigned_character_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        assigned_character_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        assigned_character_frame_wrapper.pack_propagate(False)

        # Assigned Tags Frame inside wrapper
        self.assigned_character_tags_frame = ctk.CTkScrollableFrame(assigned_character_frame_wrapper)
        self.assigned_character_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Potential Tags Frame
        all_character_tag_label = ctk.CTkLabel(tags_tab, text="Available Character Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        all_character_tag_label.pack(pady=(2, 1), padx=5, anchor="w")

        # Wrapping frame for potential character tags
        potential_character_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        potential_character_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        potential_character_frame_wrapper.pack_propagate(False)

        # Potential Tags Frame inside wrapper
        self.potential_character_tags_frame = ctk.CTkScrollableFrame(potential_character_frame_wrapper)
        self.potential_character_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Search/Add Input for Character Tags
        self.character_tag_search_var = ctk.StringVar()
        character_tag_frame = ctk.CTkFrame(tags_tab, fg_color="transparent")
        character_tag_frame.pack(fill="x", padx=10, pady=(1, 2))

        character_tag_entry = ctk.CTkEntry(
            character_tag_frame,
            textvariable=self.character_tag_search_var,
            placeholder_text="Search or add character tags...",
            width=260,
        )
        character_tag_entry.pack(side="left", fill="x", expand=True)

        # Bind search entry events
        character_tag_entry.bind("<KeyRelease>", lambda e: self.update_tag_search_results(
            self.character_tag_search_var.get(), "character", self.potential_character_tags_frame
        ))
        character_tag_entry.bind("<Return>", lambda e: self.add_tag(self.character_tag_search_var.get(), "character"))

        # Add Tag Button
        character_add_tag_button = ctk.CTkButton(
            character_tag_frame,
            text="+",
            width=30,
            command=lambda: self.add_tag_from_input(self.character_tag_search_var, "character")
        )
        character_add_tag_button.pack(side="left", padx=(5, 0))

        # Load all potential character tags by default
        self.update_tag_search_results("", "character", self.potential_character_tags_frame)

        # Model/API Tags Section
        model_api_tag_label = ctk.CTkLabel(tags_tab, text="Assigned Model/API Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        model_api_tag_label.pack(pady=2, padx=5, anchor="w")

        # Wrapping frame for assigned model/API tags
        assigned_model_api_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        assigned_model_api_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        assigned_model_api_frame_wrapper.pack_propagate(False)

        # Assigned Tags Frame inside wrapper
        self.assigned_model_api_tags_frame = ctk.CTkScrollableFrame(assigned_model_api_frame_wrapper)
        self.assigned_model_api_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Model/API Tags Section
        all_model_api_tag_label = ctk.CTkLabel(tags_tab, text="Available Model/API Tags:", font=ctk.CTkFont(size=12, weight="bold"))
        all_model_api_tag_label.pack(pady=2, padx=5, anchor="w")

        # Wrapping frame for potential model/API tags
        potential_model_api_frame_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        potential_model_api_frame_wrapper.pack(fill="x", padx=10, pady=(0, 1))

        # Disable propagation of size changes
        potential_model_api_frame_wrapper.pack_propagate(False)

        # Potential Tags Frame inside wrapper
        self.potential_model_api_tags_frame = ctk.CTkScrollableFrame(potential_model_api_frame_wrapper)
        self.potential_model_api_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Search/Add Input for Model/API Tags
        self.model_api_tag_search_var = ctk.StringVar()
        model_api_tag_frame = ctk.CTkFrame(tags_tab, fg_color="transparent")
        model_api_tag_frame.pack(fill="x", padx=0, pady=(1, 1))

        model_api_tag_entry = ctk.CTkEntry(
            model_api_tag_frame,
            textvariable=self.model_api_tag_search_var,
            placeholder_text="Search or add model/api tags...",
            placeholder_text_color="#ffffff",
            width=260,
        )
        model_api_tag_entry.pack(side="left", fill="x", expand=True)

        # Bind search entry events
        model_api_tag_entry.bind("<KeyRelease>", lambda e: self.update_tag_search_results(
            self.model_api_tag_search_var.get(), "model_api", self.potential_model_api_tags_frame
        ))
        model_api_tag_entry.bind("<Return>", lambda e: self.add_tag(self.model_api_tag_search_var.get(), "model_api"))

        # Add Tag Button
        model_api_add_tag_button = ctk.CTkButton(
            model_api_tag_frame,
            text="+",
            width=30,
            command=lambda: self.add_tag_from_input(self.model_api_tag_search_var, "model_api")
        )
        model_api_add_tag_button.pack(side="left", padx=(5, 0))

        # Load all potential model/API tags by default
        self.update_tag_search_results("", "model_api", self.potential_model_api_tags_frame)


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

        # Bind mouse wheel scrolling for main scrollable frames
        self.bind_mouse_wheel(self.scrollable_frame)  # Character list
        self.bind_mouse_wheel(self.edit_panel)  # Edit panel
        self.bind_mouse_wheel(self.extra_images_frame)  # Extra Images

        # Related Characters
        self.bind_mouse_wheel(self.related_characters_frame)

        # Tags
        self.bind_mouse_wheel(self.assigned_character_tags_frame)
        self.bind_mouse_wheel(self.potential_character_tags_frame)
        self.bind_mouse_wheel(self.assigned_model_api_tags_frame)
        self.bind_mouse_wheel(self.potential_model_api_tags_frame)

        # Automatically select the first character if none is selected
        if not hasattr(self, "selected_character_id") and self.filtered_characters:
            first_character_id = self.filtered_characters[0]["id"]
            self.select_character_by_id(first_character_id)


    def bind_mouse_wheel(self, frame, parent_frame=None):
        """Bind the mouse wheel event to a CTkScrollableFrame and prioritize it when hovered."""
        def _on_mouse_wheel(event):
            # Scroll the frame
            if frame._parent_canvas:
                frame._parent_canvas.yview_scroll(-1 * int(event.delta / 10), "units")
            return "break"

        def _bind_to_mouse_wheel(_):
            frame.bind_all("<MouseWheel>", _on_mouse_wheel)

        def _unbind_from_mouse_wheel(_):
            frame.unbind_all("<MouseWheel>")
            if parent_frame:
                parent_frame.bind_all("<MouseWheel>", _on_mouse_wheel)

        # Bind events for when the mouse enters or leaves the frame
        frame.bind("<Enter>", _bind_to_mouse_wheel)
        frame.bind("<Leave>", _unbind_from_mouse_wheel)

        # Also bind to the parent frame if provided
        if parent_frame:
            parent_frame.bind("<Enter>", lambda _: parent_frame.bind_all("<MouseWheel>", _on_mouse_wheel))


    def search_tags(self, query, category):
        """Search globally available tags."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name FROM tags WHERE category = ? AND name LIKE ?
        """, (category, f"%{query}%"))
        tags = [row[0] for row in cursor.fetchall()]

        connection.close()
        return tags
    

    def update_tag_search_results(self, query, category, frame):
        """Update the potential tag search results dynamically, excluding assigned tags."""
        # Clear the frame
        for widget in frame.winfo_children():
            widget.destroy()

        # Fetch all tags matching the category
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()

        # Get tags already assigned to the character
        assigned_tags = set()
        if hasattr(self, "selected_character_id"):
            cursor.execute("""
                SELECT t.name FROM tags t
                INNER JOIN character_tags ct ON t.id = ct.tag_id
                WHERE ct.character_id = ? AND t.category = ?
            """, (self.selected_character_id, category))
            assigned_tags = {row[0] for row in cursor.fetchall()}

        # Fetch all potential tags
        if query.strip():
            cursor.execute("""
                SELECT name FROM tags WHERE category = ? AND name LIKE ?
            """, (category, f"%{query.strip()}%"))
        else:
            cursor.execute("""
                SELECT name FROM tags WHERE category = ?
            """, (category,))
        all_tags = [row[0] for row in cursor.fetchall()]
        connection.close()

        # Exclude assigned tags
        potential_tags = [tag for tag in all_tags if tag not in assigned_tags]

        # Display the potential tags
        for tag in potential_tags:
            tag_frame = ctk.CTkFrame(frame, corner_radius=5)
            tag_frame.pack(pady=2, padx=5, fill="x")

            tag_label = ctk.CTkLabel(tag_frame, text=tag, anchor="w")
            tag_label.pack(side="left", padx=5)

            # Use functools.partial to pass arguments correctly
            add_button = ctk.CTkButton(
                tag_frame,
                text="+",
                width=30,
                command=partial(self.add_tag, tag, category)
            )
            add_button.pack(side="right", padx=1)



    def load_tags(self):
        """Load tags for the selected character."""
        if not hasattr(self, "selected_character_id"):
            self.clear_tags()
            return

        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()

        # Fetch character tags
        cursor.execute("""
            SELECT t.name FROM tags t
            INNER JOIN character_tags ct ON t.id = ct.tag_id
            WHERE ct.character_id = ? AND t.category = 'character'
        """, (self.selected_character_id,))
        character_tags = [row[0] for row in cursor.fetchall()]

        # Fetch model/API tags
        cursor.execute("""
            SELECT t.name FROM tags t
            INNER JOIN character_tags ct ON t.id = ct.tag_id
            WHERE ct.character_id = ? AND t.category = 'model_api'
        """, (self.selected_character_id,))
        model_api_tags = [row[0] for row in cursor.fetchall()]

        connection.close()

        # Display assigned tags
        self.display_tags(self.assigned_character_tags_frame, character_tags, "character")
        self.display_tags(self.assigned_model_api_tags_frame, model_api_tags, "model_api")


    def display_tags(self, frame, tags, category):
        """Display tags in the specified frame."""
        for widget in frame.winfo_children():
            widget.destroy()

        for tag in tags:
            tag_frame = ctk.CTkFrame(frame, corner_radius=5)
            tag_frame.pack(pady=2, padx=5, fill="x")

            tag_label = ctk.CTkLabel(tag_frame, text=tag, anchor="w")
            tag_label.pack(side="left", padx=5)

            delete_button = ctk.CTkButton(
                tag_frame,
                text="X",
                width=30,
                fg_color="red",
                command=lambda tag_name=tag: self.remove_tag(tag_name, category)
            )
            delete_button.pack(side="right", padx=1)

    def clear_tags(self):
        """Clear all tags displayed in the tag frames."""
        for frame in [
            self.assigned_character_tags_frame, self.potential_character_tags_frame,
            self.assigned_model_api_tags_frame, self.potential_model_api_tags_frame
        ]:
            for widget in frame.winfo_children():
                widget.destroy()

    def add_tag_from_input(self, tag_var, category):
        """Add a new tag from the search input field, assign it, and clear the input."""
        tag_name = tag_var.get().strip()
        if not tag_name:
            self.show_message("Tag name cannot be empty.", "error")
            return

        try:
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()

            # Check if the tag already exists globally
            cursor.execute("SELECT id FROM tags WHERE name = ? AND category = ?", (tag_name, category))
            tag = cursor.fetchone()

            if tag:
                # Tag already exists
                tag_id = tag[0]
            else:
                # Add the tag globally if it doesn't exist
                cursor.execute("INSERT INTO tags (name, category) VALUES (?, ?)", (tag_name, category))
                connection.commit()
                tag_id = cursor.lastrowid

            # Associate the tag with the selected character
            if hasattr(self, "selected_character_id"):
                cursor.execute("""
                    INSERT OR IGNORE INTO character_tags (character_id, tag_id) VALUES (?, ?)
                """, (self.selected_character_id, tag_id))
                connection.commit()

            # Clear the search input field
            tag_var.set("")

            # Refresh assigned and potential tags
            self.load_tags()
            if category == "character":
                self.update_tag_search_results("", "character", self.potential_character_tags_frame)
            elif category == "model_api":
                self.update_tag_search_results("", "model_api", self.potential_model_api_tags_frame)

            self.show_message(f"Tag '{tag_name}' added and assigned successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to add and assign tag: {e}", "error")

        finally:
            connection.close()


    def add_tag(self, tag_name, category):
        """Add a tag globally and associate it with the selected character."""
        if not tag_name.strip():
            return

        try:
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()

            # Insert the tag globally if it doesn't already exist
            cursor.execute("""
                INSERT OR IGNORE INTO tags (name, category) VALUES (?, ?)
            """, (tag_name, category))

            # Get the tag ID
            cursor.execute("SELECT id FROM tags WHERE name = ? AND category = ?", (tag_name, category))
            tag_id = cursor.fetchone()[0]

            # Associate the tag with the selected character
            if hasattr(self, "selected_character_id"):
                cursor.execute("""
                    INSERT OR IGNORE INTO character_tags (character_id, tag_id) VALUES (?, ?)
                """, (self.selected_character_id, tag_id))

            connection.commit()
            connection.close()

            # Refresh assigned and potential tags
            self.load_tags()
            if category == "character":
                self.update_tag_search_results(self.character_tag_search_var.get(), "character", self.potential_character_tags_frame)
            elif category == "model_api":
                self.update_tag_search_results(self.model_api_tag_search_var.get(), "model_api", self.potential_model_api_tags_frame)

        except Exception as e:
            print(f"Error adding tag: {e}")


    def remove_tag(self, tag_name, category):
        """Remove a tag association from the selected character."""
        try:
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()

            # Get the tag ID
            cursor.execute("SELECT id FROM tags WHERE name = ? AND category = ?", (tag_name, category))
            tag_id = cursor.fetchone()
            if tag_id:
                tag_id = tag_id[0]

                # Delete the character-tag association
                cursor.execute("""
                    DELETE FROM character_tags WHERE character_id = ? AND tag_id = ?
                """, (self.selected_character_id, tag_id))

                connection.commit()

            connection.close()

            # Refresh tags
            self.load_tags()

            # Refresh potential tags to include the removed tag
            if category == "character":
                self.update_tag_search_results(self.character_tag_search_var.get(), "character", self.potential_character_tags_frame)
            elif category == "model_api":
                self.update_tag_search_results(self.model_api_tag_search_var.get(), "model_api", self.potential_model_api_tags_frame)

        except Exception as e:
            print(f"Error removing tag: {e}")



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

            # Clear the currently selected character in the sidebar
            self.clear_selected_character_sidebar()

            # Clear the edit panel (ensure widgets exist before clearing)
            if hasattr(self, "name_entry") and self.name_entry.winfo_exists():
                self.clear_edit_panel()

            # Show success message
            self.show_message("Character deleted successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to delete character: {str(e)}", "error")



    def remove_character_from_list(self, character_id):
        """Remove the character from the in-memory lists and refresh the UI."""
        try:
            # Remove from the all_characters list
            self.all_characters = [char for char in self.all_characters if char["id"] != character_id]

            # Remove from the filtered_characters list
            self.filtered_characters = [char for char in self.filtered_characters if char["id"] != character_id]

            # Recalculate total pages and reset to the current page
            self.total_pages = (len(self.filtered_characters) + self.items_per_page - 1) // self.items_per_page
            if self.current_page >= self.total_pages:
                self.current_page = max(self.total_pages - 1, 0)  # Ensure valid page index

            # Refresh the UI
            self.display_characters()
            self.update_navigation_buttons()

            # Debugging output
            print(f"Character ID: {character_id} removed from lists.")
        except Exception as e:
            print(f"Error removing character from list: {str(e)}")


    def clear_selected_character_sidebar(self):
        """Clear the currently selected character details from the sidebar."""
        if self.selected_character_frame:
            # Destroy all child widgets inside the selected character frame
            for widget in self.selected_character_frame.winfo_children():
                widget.destroy()

            # Hide the frame
            self.selected_character_frame.pack_forget()


    def clear_edit_panel(self):
        """Clear the edit panel fields."""
        if hasattr(self, "name_entry") and self.name_entry.winfo_exists():
            self.name_entry.delete(0, "end")

        if hasattr(self, "main_file_label") and self.main_file_label.winfo_exists():
            self.main_file_label.configure(text="Main File: ")

        if hasattr(self, "notes_textbox") and self.notes_textbox.winfo_exists():
            self.notes_textbox.delete("1.0", "end")

        if hasattr(self, "misc_notes_textbox") and self.misc_notes_textbox.winfo_exists():
            self.misc_notes_textbox.delete("1.0", "end")

        if hasattr(self, "created_date_label") and self.created_date_label.winfo_exists():
            self.created_date_label.configure(text="Created: ")

        if hasattr(self, "last_modified_date_label") and self.last_modified_date_label.winfo_exists():
            self.last_modified_date_label.configure(text="Last Modified: ")

        self.selected_character_id = None

    def add_character(self):
        """Open a new window to add a character."""
        # Create the modal window using CTkToplevel
        self.add_character_window = ctk.CTkToplevel(self)
        self.add_character_window.title("Add Character")
        self.add_character_window.geometry("400x350")

        # Ensure the modal stays on top of the main window
        self.add_character_window.transient(self)  # Set to be a child of the main window
        self.add_character_window.grab_set()       # Block interaction with the main window

        # Align the modal to the top-left corner of the main window
        self._align_modal_top_left(self.add_character_window)

        # Scrollable Frame for the Form
        scrollable_frame = ctk.CTkScrollableFrame(self.add_character_window, width=380, height=380)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=2)

        # Message Banner
        self.add_character_message_banner = ctk.CTkLabel(
            self.add_character_window, text="", height=30, fg_color="#FFCDD2", corner_radius=5, text_color="black"
        )
        self.add_character_message_banner.pack(fill="x", padx=10, pady=(2, 0))
        self.add_character_message_banner.pack_forget()  # Hide initially

        # File Upload Section
        file_frame = ctk.CTkFrame(scrollable_frame)
        file_frame.pack(fill="x", pady=2, padx=10, anchor="w")

        file_label = ctk.CTkLabel(file_frame, text="Upload File:", anchor="w")
        file_label.pack(side="left", padx=5)

        self.file_path_entry = ctk.CTkEntry(file_frame, placeholder_text="Select File", width=240)
        self.file_path_entry.pack(side="left", padx=5)

        browse_button = ctk.CTkButton(file_frame, text="Browse", width=100, command=self.browse_file)
        browse_button.pack(side="left", padx=5)

        # Character Name Section
        name_frame = ctk.CTkFrame(scrollable_frame)
        name_frame.pack(fill="x", pady=2, padx=10)

        name_label = ctk.CTkLabel(name_frame, text="Character Name:", anchor="w")
        name_label.pack(side="left", padx=5)

        self.add_character_name_entry = ctk.CTkEntry(name_frame, placeholder_text="Default: File Name", width=240)
        self.add_character_name_entry.pack(side="left", padx=5)

        # Character Notes
        notes_label = ctk.CTkLabel(scrollable_frame, text="Character Notes:", anchor="w")
        notes_label.pack(pady=10, padx=10, anchor="w")
        self.add_character_notes_textbox = ctk.CTkTextbox(scrollable_frame, height=100)
        self.add_character_notes_textbox.pack(pady=0, padx=10, fill="x")

        # Miscellaneous Notes
        misc_notes_label = ctk.CTkLabel(scrollable_frame, text="Miscellaneous Notes:", anchor="w")
        misc_notes_label.pack(pady=10, padx=10, anchor="w")
        self.add_misc_notes_textbox = ctk.CTkTextbox(scrollable_frame, height=100)
        self.add_misc_notes_textbox.pack(pady=0, padx=10, fill="x")

        # Automatically add to SillyTavern Checkbox (hidden initially)
        self.auto_add_checkbox = ctk.CTkCheckBox(
            scrollable_frame,
            text="Automatically add card to SillyTavern?",
            state="disabled"
        )
        self.auto_add_checkbox.pack(pady=10, padx=10, anchor="w")
        self.auto_add_checkbox.pack_forget()  # Hide initially

        # Submit Button
        submit_button = ctk.CTkButton(scrollable_frame, text="Add Character", command=self.save_character_with_message)
        submit_button.pack(pady=5, padx=10, anchor="w")
        
        # API Import Section
        api_frame = ctk.CTkFrame(self.add_character_window)
        api_frame.pack(fill="x", pady=10, padx=10)

        api_label = ctk.CTkLabel(api_frame, text="AICC Card ID:", anchor="w")
        api_label.pack(side="left", padx=5)

        self.card_id_entry = ctk.CTkEntry(api_frame, placeholder_text="e.g., AICC/aicharcards/the-game-master", width=240)
        self.card_id_entry.pack(side="left", padx=5)

        import_button = ctk.CTkButton(api_frame, text="Import", command=self.import_aicc_card)
        import_button.pack(side="left", padx=5)

        # Bind the mouse wheel to the scrollable frame
        self.bind_mouse_wheel(scrollable_frame)

    def _align_modal_top_left(self, window):
        """Align the modal to the top-left corner of the main window."""
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()

        # Get the position of the parent window
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()

        # Set the modal position relative to the top-left corner of the parent window
        x = parent_x
        y = parent_y
        window.geometry(f"{width}x{height}+{x}+{y}")


    def import_aicc_card(self):
        """Import a card from AICC and handle only the file import."""
        card_id = self.card_id_entry.get().strip()
        if not card_id:
            self.show_add_character_message("Please enter a valid Card ID.", "error")
            return

        try:
            # Fetch the card details from AICC
            downloaded_file = AICCImporter.fetch_card(card_id)

            # Populate only the file path field
            self.file_path_entry.delete(0, "end")
            self.file_path_entry.insert(0, downloaded_file)

            # Show success message
            self.show_add_character_message("Card imported successfully. Fill in other details before saving.", "success")

        except Exception as e:
            self.show_add_character_message(f"Error importing card: {str(e)}", "error")


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
            self.add_character_name_entry.delete(0, "end")
            self.add_character_name_entry.insert(0, default_name)


    def export_data(self):
        print("Export Data clicked")


    def update_currently_selected_character(self, character_name, image_path):
        """Update the sidebar with the currently selected character."""
        # Ensure the frame exists
        if self.selected_character_frame is None:
            self.selected_character_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent", width=200)
            self.selected_character_frame.pack(pady=10, padx=0, fill="x")

        # Clear any previous content in the frame
        for widget in self.selected_character_frame.winfo_children():
            widget.destroy()

        # Add title label
        title_label = ctk.CTkLabel(self.selected_character_frame, text="Currently Selected Character",
                                font=ctk.CTkFont(size=14, weight="bold"))
        title_label.pack(pady=(0, 5))

        # Add character name label
        name_label = ctk.CTkLabel(self.selected_character_frame, text=character_name, font=ctk.CTkFont(size=16, weight="bold"))
        name_label.pack(pady=(0, 10))

        # Add character image
        try:
            img = Image.open(image_path)

            # Resize to fit within sidebar
            max_width = 200
            aspect_ratio = img.width / img.height
            new_height = int(max_width / aspect_ratio)

            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            ctk_image = ctk.CTkImage(img, size=(max_width, new_height))
        except Exception as e:
            print(f"Error loading character image: {e}")
            # Use a default image in case of error
            default_image_path = "assets/default_thumbnail.png"
            ctk_image = ctk.CTkImage(Image.open(default_image_path), size=(200, 300))

        image_label = ctk.CTkLabel(self.selected_character_frame, image=ctk_image, text="")
        image_label.image = ctk_image  # Keep a reference to avoid garbage collection
        image_label.pack()



    def save_changes(self):
        """Save changes made in the edit panel to the database."""
        try:
            # Validate that widgets still exist
            if not all([
                self.name_entry.winfo_exists(),
                self.main_file_label.winfo_exists(),
                self.notes_textbox.winfo_exists(),
                self.misc_notes_textbox.winfo_exists()
            ]):
                self.show_message("The edit panel has been refreshed or is invalid. Please select the character again.", "error")
                return

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

            # Ensure a character is selected
            if not hasattr(self, "selected_character_id"):
                self.show_message("No character selected for saving changes.", "error")
                return

            # Debugging: Print the ID being updated
            print(f"Updating character ID: {self.selected_character_id}")

            # Update the database record
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE characters
                SET name = ?, notes = ?, misc_notes = ?, last_modified_date = ?
                WHERE id = ?
                """,
                (character_name, notes, misc_notes, last_modified_date, self.selected_character_id)
            )
            connection.commit()
            connection.close()

            # Update the internal list dynamically
            for character in self.all_characters:
                if character["id"] == self.selected_character_id:
                    character["name"] = character_name
                    character["last_modified_date"] = last_modified_date
                    break

            # Sort the list if required
            sort_option = self.sort_var.get()
            self.sort_character_list(sort_option)

            # Find the updated character's index in the filtered list
            new_index = next(
                (index for index, char in enumerate(self.filtered_characters) if char["id"] == self.selected_character_id),
                0
            )

            # Calculate the page the character belongs to
            self.current_page = new_index // self.items_per_page

            # Refresh the UI
            self.display_characters()
            self.update_navigation_buttons()

            # Highlight the updated character
            self.highlight_selected_character(self.selected_character_id)

            # Show success message
            self.show_message("Changes saved successfully.", "success")
        except Exception as e:
            self.show_message(f"Failed to save changes: {str(e)}", "error")

    def select_character_by_id(self, character_id):
        """Handle character selection by ID and populate the edit panel."""
        print(character_id)
        try:
            # Fetch character details from the database
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
                # Extract data
                self.selected_character_id = result[0]
                name, main_file, notes, misc_notes, created_date, last_modified_date = result[1:]

                # Handle None values
                notes = notes or ""
                misc_notes = misc_notes or ""

                # Debugging: Print fetched values
                # print(name)
                # print(notes)
                # print(misc_notes)
                # print(created_date)
                # print(last_modified_date)
                # print(main_file)

                # Unified UI update
                fields_to_update = {
                    "name_entry": (name, "entry"),
                    "main_file_label": (f"Main File: {main_file}", "label"),
                    "notes_textbox": (notes, "textbox"),
                    "misc_notes_textbox": (misc_notes, "textbox"),
                    "created_date_label": (
                        f"Created: {datetime.strptime(created_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}",
                        "label",
                    ),
                    "last_modified_date_label": (
                        f"Last Modified: {datetime.strptime(last_modified_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}",
                        "label",
                    ),
                }

                for field_name, (value, field_type) in fields_to_update.items():
                    if hasattr(self, field_name):
                        field = getattr(self, field_name)
                        if field.winfo_exists():
                            if field_type == "entry":
                                field.delete(0, "end")
                                field.insert(0, value)
                            elif field_type == "label":
                                field.configure(text=value)
                            elif field_type == "textbox":
                                field.delete("1.0", "end")
                                field.insert("1.0", value)
                            field.update_idletasks()  # Force the UI to refresh
                        else:
                            print(f"{field_name} does not exist or is not accessible.")
                    else:
                        print(f"{field_name} is not a valid attribute.")

                # Load extra images for the selected character
                self.extra_images_manager.load_extra_images(
                    self.selected_character_id,
                    self.extra_images_frame,
                    self.create_thumbnail
                )

                self.load_related_characters()
                self.load_tags()

                # Update the currently selected character in the sidebar
                image_path = os.path.join("CharacterCards", name, main_file) if main_file else "assets/default_thumbnail.png"
                self.update_currently_selected_character(name, image_path)

                # Highlight the selected character in the list
                self.highlight_selected_character(character_id)

                # Set the tabview to the "Notes" tab
                if hasattr(self, "edit_panel"):
                    for widget in self.edit_panel.winfo_children():
                        if isinstance(widget, ctk.CTkTabview):
                            widget.set("Notes")  # Set the active tab to "Notes"
                            break


            else:
                # Handle case where the character does not exist
                self.clear_edit_panel()
                self.show_message("Character not found. Please refresh the list.", "error")

        except Exception as e:
            print(f"Error in select_character_by_id: {e}")


    def highlight_selected_character(self, selected_id):
        """Highlight the selected character in the list with a light purple border."""
        for widget in self.scrollable_frame.winfo_children():
            if hasattr(widget, "character_id"):
                if widget.character_id == selected_id:
                    # Apply the light purple border to the selected character
                    widget.configure(border_color="#D8BFD8", border_width=2)  # Light purple border

                    widget.configure(fg_color="#D8BFD8")  # Light purple background

                    # Schedule a return to the original color after 2 seconds
                    self.after(100, lambda w=widget: w.configure(fg_color="#212121"))
                else:
                    # Reset the border for unselected characters
                    widget.configure(border_color="", border_width=0)



    def update_edit_panel(self, name, main_file, notes, misc_notes, created_date, last_modified_date):
        """Update the edit panel fields."""
        # Update character name
        if self.name_entry.winfo_exists():
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, name)

        # Update main file label
        if self.main_file_label.winfo_exists():
            self.main_file_label.configure(text=f"Main File: {main_file}")

        # Update character notes
        if self.notes_textbox.winfo_exists():
            self.notes_textbox.delete("1.0", "end")
            self.notes_textbox.insert("1.0", notes)

        # Update miscellaneous notes
        if self.misc_notes_textbox.winfo_exists():
            self.misc_notes_textbox.delete("1.0", "end")  # Clear previous data
            self.misc_notes_textbox.insert("1.0", misc_notes)  # Set misc_notes correctly

        # Update created and modified dates
        if self.created_date_label.winfo_exists():
            self.created_date_label.configure(
                text=f"Created: {datetime.strptime(created_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}"
            )

        if self.last_modified_date_label.winfo_exists():
            self.last_modified_date_label.configure(
                text=f"Last Modified: {datetime.strptime(last_modified_date, '%Y-%m-%d %H:%M:%S').strftime('%m/%d/%Y %I:%M %p')}"
            )


    def format_date(self, date_string):
        """Format a date string for display."""
        try:
            date_obj = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            return date_obj.strftime("%m/%d/%Y %I:%M %p")
        except Exception:
            return "Unknown Date"


    def update_character_list(self, character_id, character_name, last_modified_date):
        """Update the character list dynamically after changes."""
        formatted_date = datetime.strptime(last_modified_date, "%Y-%m-%d %H:%M:%S").strftime("%m/%d/%Y %I:%M %p")
        
        # Update the specific character in the list
        for character in self.all_characters:
            if character["id"] == character_id:
                character["name"] = character_name
                character["last_modified_date"] = last_modified_date
                break

        # Sort the list alphabetically by name (optional, depending on UI requirements)
        self.all_characters.sort(key=lambda char: char["name"].lower())

        # Refresh filtered characters and pagination
        self.filtered_characters = self.all_characters
        self.total_pages = (len(self.filtered_characters) + self.items_per_page - 1) // self.items_per_page
        self.current_page = 0  # Reset to the first page

        # Refresh UI
        self.display_characters()
        self.update_navigation_buttons()

        # Update UI for the specific character in the scrollable frame
        for widget in self.scrollable_frame.winfo_children():
            if hasattr(widget, "character_id") and widget.character_id == character_id:
                for sub_widget in widget.winfo_children():
                    if isinstance(sub_widget, ctk.CTkLabel):
                        if sub_widget.cget("text").startswith("Last Modified:"):
                            sub_widget.configure(text=f"Last Modified: {formatted_date}")
                        elif sub_widget.cget("text") == widget.character_name:
                            sub_widget.configure(text=character_name)

                # Update internal attributes for consistency
                widget.character_name = character_name

                # Rebind click events for the updated frame and its children
                for sub_widget in widget.winfo_children():
                    sub_widget.bind("<Button-1>", lambda e, char_id=character_id: self.select_character_by_id(char_id))
                widget.bind("<Button-1>", lambda e, char_id=character_id: self.select_character_by_id(char_id))
                return


    def save_character_with_message(self):
        """Save the character to the database and filesystem, with messages."""
        file_path = self.file_path_entry.get().strip()  # File browser path
        character_name = self.add_character_name_entry.get().strip()
        character_notes = self.add_character_notes_textbox.get("1.0", "end").strip()
        misc_notes = self.add_misc_notes_textbox.get("1.0", "end").strip()

        # Validate character name
        if not character_name:
            self.show_add_character_message("Please provide a character name.", "error")
            return

        # Validate that either a file or an imported PNG exists
        if not file_path and not hasattr(self, "imported_png_path"):
            self.show_add_character_message("Please select a file or import a card via the API.", "error")
            return

        # Check for duplicate character name
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM characters WHERE name = ?", (character_name,))
        if cursor.fetchone()[0] > 0:
            self.show_add_character_message("Character name already exists. Please choose another name.", "error")
            connection.close()
            return

        # Create the character directory
        character_dir = os.path.join("CharacterCards", character_name)
        os.makedirs(character_dir, exist_ok=True)

        try:
            # Handle file from the file browser
            if file_path:
                final_file_path = os.path.join(character_dir, os.path.basename(file_path))
                shutil.copy(file_path, final_file_path)

            # Handle imported PNG via API
            elif hasattr(self, "imported_png_path") and os.path.exists(self.imported_png_path):
                final_file_path = os.path.join(character_dir, f"{character_name}.png")
                shutil.move(self.imported_png_path, final_file_path)
                del self.imported_png_path  # Clean up the attribute after use

            else:
                raise ValueError("No valid file found for saving.")

            # Generate timestamps
            created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last_modified_date = created_date

            # Add character data to the database
            cursor.execute(
                """INSERT INTO characters 
                (name, main_file, notes, misc_notes, created_date, last_modified_date) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (character_name, os.path.basename(final_file_path), character_notes, misc_notes, created_date, last_modified_date),
            )
            connection.commit()

            # Get the newly created character ID
            new_character_id = cursor.lastrowid
            connection.close()

            # Add the character to the in-memory list
            self.all_characters.append({
                "id": new_character_id,
                "name": character_name,
                "image_path": final_file_path,
                "created_date": created_date,
                "last_modified_date": last_modified_date,
            })

            # Reapply sorting based on the current sort option
            self.sort_character_list(self.sort_var.get())

            # Find the new character's index in the sorted list
            new_character_index = next(
                (index for index, char in enumerate(self.filtered_characters) if char["id"] == new_character_id),
                0
            )

            # Calculate the page for the new character
            self.total_pages = (len(self.filtered_characters) + self.items_per_page - 1) // self.items_per_page
            self.current_page = new_character_index // self.items_per_page

            # Refresh the displayed characters
            self.display_characters()
            self.update_navigation_buttons()

            # Highlight the new character
            self.select_character_by_id(new_character_id)


            # Show success message and close the modal
            self.show_add_character_message("Character added successfully!", "success")
            self.add_character_window.after(500, self.add_character_window.destroy())

        except Exception as e:
            self.show_add_character_message(f"Error saving character: {str(e)}", "error")



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
    

    def filter_related_characters(self):
        """Filter the list of related characters based on the search query."""
        query = self.related_search_var.get().lower().strip()
        if not query:
            # Display all related characters if no query
            self.display_related_characters()
        else:
            # Filter related characters
            filtered = [
                char for char in self.related_characters
                if query in char["name"].lower()
            ]
            self.display_related_characters(filtered)

    def display_related_characters(self, characters=None):
        """Display the related characters in the scrollable frame."""
        characters = characters or self.related_characters

        # Clear current display
        for widget in self.related_characters_frame.winfo_children():
            widget.destroy()

        for char in characters:
            char_frame = ctk.CTkFrame(self.related_characters_frame, corner_radius=5)
            char_frame.pack(pady=5, padx=5, fill="x")

            # Thumbnail
            thumbnail = self.create_thumbnail(char["image_path"])
            thumbnail_label = ctk.CTkLabel(char_frame, image=thumbnail, text="")
            thumbnail_label.image = thumbnail  # Prevent garbage collection
            thumbnail_label.grid(row=0, column=0, padx=5)

            # Character Name
            name_label = ctk.CTkLabel(char_frame, text=char["name"], anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
            name_label.grid(row=0, column=1, sticky="w", padx=5)

            # Jump to Character Button
            jump_button = ctk.CTkButton(
                char_frame,
                text="Select",
                command=lambda char_id=char["id"]: self.select_character_by_id(char_id),
            )
            jump_button.grid(row=0, column=2, padx=5)

            # Unlink Button
            unlink_button = ctk.CTkButton(
                char_frame,
                text="X",
                fg_color="red",
                command=lambda char_id=char["id"]: self.unlink_character(char_id),
            )
            unlink_button.grid(row=0, column=3, padx=5)


    def load_related_characters(self):
        """Load related characters for the selected character."""
        if not hasattr(self, "selected_character_id"):
            self.related_characters = []
            return

        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.main_file
            FROM characters c
            JOIN character_relationships r ON c.id = r.related_character_id
            WHERE r.character_id = ?
        """, (self.selected_character_id,))
        rows = cursor.fetchall()
        connection.close()

        # Process characters into a usable format
        self.related_characters = [
            {
                "id": row[0],
                "name": row[1],
                "image_path": os.path.join("CharacterCards", row[1], row[2])
            }
            for row in rows
        ]

        # Display the related characters
        self.display_related_characters()

    def open_link_character_modal(self):
        """Open a modal to search and link a new character."""
        modal = ctk.CTkToplevel(self)
        modal.title("Link Character")
        modal.geometry("400x400")

        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(modal, textvariable=search_var, placeholder_text="Search characters...", width=300)
        search_entry.pack(pady=(10, 5), padx=10)

        # Scrollable Frame for Character List
        scrollable_frame = ctk.CTkScrollableFrame(modal, height=300)
        scrollable_frame.pack(fill="both", expand=True, padx=0, pady=5)
        
        # Inside open_link_character_modal
        self.bind_mouse_wheel(scrollable_frame)  # Link Character Modal's scrollable frame


        def filter_and_display():
            query = search_var.get().lower().strip()
            characters = self.get_character_list()
            # Exclude the currently selected character
            characters = [char for char in characters if char["id"] != self.selected_character_id]
            if query:
                characters = [char for char in characters if query in char["name"].lower()]
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            for char in characters:
                char_frame = ctk.CTkFrame(scrollable_frame, corner_radius=5)
                char_frame.pack(pady=5, padx=5, fill="x")

                # Thumbnail
                thumbnail = self.create_thumbnail(char["image_path"])
                thumbnail_label = ctk.CTkLabel(char_frame, image=thumbnail, text="")
                thumbnail_label.image = thumbnail
                thumbnail_label.grid(row=0, column=0, padx=5)

                # Character Name
                name_label = ctk.CTkLabel(char_frame, text=char["name"], anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
                name_label.grid(row=0, column=1, sticky="w", padx=5)

                # Link Button
                link_button = ctk.CTkButton(
                    char_frame,
                    text="Link",
                    command=lambda char_id=char["id"]: self.link_character(char_id, modal),
                )
                link_button.grid(row=0, column=2, padx=5)

        search_var.trace_add("write", lambda *args: filter_and_display())
        filter_and_display()
    

    def link_character(self, related_character_id, modal):
        """Link a character to the currently selected character."""
        if not hasattr(self, "selected_character_id"):
            self.show_message("No character selected to link.", "error")
            return

        try:
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()

            # Ensure the characters aren't already linked
            cursor.execute("""
                SELECT COUNT(*) FROM character_relationships 
                WHERE (character_id = ? AND related_character_id = ?)
                OR (character_id = ? AND related_character_id = ?)
            """, (self.selected_character_id, related_character_id,
                related_character_id, self.selected_character_id))
            if cursor.fetchone()[0] > 0:
                self.show_message("These characters are already linked.", "error")
                connection.close()
                return

            # Insert bi-directional relationships
            cursor.execute("""
                INSERT INTO character_relationships (character_id, related_character_id)
                VALUES (?, ?)
            """, (self.selected_character_id, related_character_id))
            cursor.execute("""
                INSERT INTO character_relationships (character_id, related_character_id)
                VALUES (?, ?)
            """, (related_character_id, self.selected_character_id))
            connection.commit()
            connection.close()

            # Refresh related characters
            self.load_related_characters()
            modal.destroy()
            self.show_message("Character linked successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to link character: {e}", "error")

    def unlink_character(self, related_character_id):
        """Unlink a related character."""
        try:
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()

            # Delete relationships in both directions
            cursor.execute("""
                DELETE FROM character_relationships 
                WHERE (character_id = ? AND related_character_id = ?)
                OR (character_id = ? AND related_character_id = ?)
            """, (self.selected_character_id, related_character_id,
                related_character_id, self.selected_character_id))
            connection.commit()
            connection.close()

            # Refresh related characters
            self.load_related_characters()
            self.show_message("Character unlinked successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to unlink character: {e}", "error")

class MultiSelectModal(ctk.CTkToplevel):
    def __init__(self, parent, title, options, selected_options, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("350x400")
        self.parent = parent
        self.options = options
        self.selected_options = set(selected_options)
        self.callback = callback
        self.items_per_page = 20
        self.current_page = 0
        self.total_pages = (len(options) + self.items_per_page - 1) // self.items_per_page

        # Ensure the modal stays on top of the parent window
        self.transient(self.parent)
        self.grab_set()

        # Align the modal to the top-left corner of the parent window
        self._align_modal_top_left(self, self.parent)

        # Header with pagination controls
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", pady=5, padx=10)

        self.page_label = ctk.CTkLabel(header_frame, text=f"Page {self.current_page + 1} of {self.total_pages}")
        self.page_label.pack(side="left", padx=5)

        prev_button = ctk.CTkButton(header_frame, text="Previous", width=80, command=self.prev_page)
        prev_button.pack(side="left", padx=5)

        next_button = ctk.CTkButton(header_frame, text="Next", width=80, command=self.next_page)
        next_button.pack(side="right", padx=5)

        # Scrollable frame for displaying options
        self.scrollable_frame = ctk.CTkScrollableFrame(self, height=300)
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Save button
        save_button = ctk.CTkButton(self, text="Save", command=self.save_selection)
        save_button.pack(pady=10)

        # Dictionary to store checkboxes
        self.check_vars = {}

        # Display the first page
        self.display_page()


    def display_page(self):
        """Display the current page of options."""
        # Clear the existing content in the scrollable frame
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        start_index = self.current_page * self.items_per_page
        end_index = min(start_index + self.items_per_page, len(self.options))

        for option in self.options[start_index:end_index]:
            var = self.check_vars.get(option, ctk.BooleanVar(value=option in self.selected_options))
            checkbox = ctk.CTkCheckBox(self.scrollable_frame, text=option, variable=var, command=self.update_selection)
            checkbox.pack(anchor="w", padx=10, pady=5)
            self.check_vars[option] = var

        # Update pagination label
        self.page_label.configure(text=f"Page {self.current_page + 1} of {self.total_pages}")

    def update_selection(self):
        """Update selected options based on checkbox states."""
        self.selected_options = {option for option, var in self.check_vars.items() if var.get()}

    def save_selection(self):
        """Save selected options and invoke callback."""
        self.callback(self.selected_options)
        self.destroy()

    def prev_page(self):
        """Go to the previous page if available."""
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page()

    def next_page(self):
        """Go to the next page if available."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_page()

    @staticmethod
    def _align_modal_top_left(window, parent):
        """Align the modal to the top-left corner of the parent window."""
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()

        # Get the position of the parent window
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()

        # Set the modal position relative to the top-left corner of the parent window
        x = parent_x
        y = parent_y
        window.geometry(f"{width}x{height}+{x}+{y}")


if __name__ == "__main__":
    app = CharacterCardManagerApp()
    app.mainloop()
