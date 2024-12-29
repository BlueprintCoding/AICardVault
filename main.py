import customtkinter as ctk
from customtkinter import CTkFont
from PIL import Image
from pathlib import Path
import os
from datetime import datetime
import shutil
import sqlite3
import json
import threading
import queue
import weakref
from utils.db_manager import DatabaseManager
from utils.file_handler import FileHandler
from datetime import datetime
from utils.extra_images import ExtraImagesManager
from utils.settings import SettingsModal
from utils.import_characters import ImportModal
from utils.aicc_site_functions import AICCImporter
from utils.st_tag_manager import TagsManager
from utils.st_tag_manager_edit_panel import SillyTavernTagManager
from utils.import_lorebooks import LorebookManager
from tkinter.filedialog import askopenfilename
from tkinter.messagebox import askyesno
from utils.card_metadata import PNGMetadataReader
from utils.lorebook_functions import (
    open_lorebooks_modal,
    display_lorebooks,
    load_lorebook_details,
    refresh_lorebooks,
    handle_lorebook_save,
    display_images,
    add_image_modal,
    edit_image,
    refresh_images,
    delete_image,
    browse_image_file,
    save_image_changes,
    open_link_character_modal_for_lorebook,
    display_linked_characters,
    get_linked_characters,
    link_character_to_lorebook,
    unlink_character_from_lorebook
)

class CharacterCardManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Card Vault")
        self.geometry("1400x710")
        ctk.set_appearance_mode("dark")  # Use system theme
        ctk.set_default_color_theme("assets/AiCardVaultTheme.json")
        self.current_page = 0  # Start at the first page
        

        # Initialize database and file handler
        self.db_manager = DatabaseManager()
        self.file_handler = FileHandler()

        # Load settings from the database
        self.settings = {
            "appearance_mode": self.db_manager.get_setting("appearance_mode", "dark"),
            "sillytavern_path": Path(self.db_manager.get_setting("sillytavern_path", "")).resolve(),
            "default_sort_order": self.db_manager.get_setting("default_sort_order", "A - Z"),
            "items_per_page": int(self.db_manager.get_setting("items_per_page", "5")),  # Default to 5 if not set
            "tags_per_page": int(self.db_manager.get_setting("tags_per_page", "10")),  # Default to 10 if not set
        }

        # Initialize SillyTavernTagManager after settings are loaded
        self.tag_manager = SillyTavernTagManager(self.settings["sillytavern_path"])

        # Ensure default sort order is set if not already present
        if not self.db_manager.get_setting("default_sort_order"):
            self.db_manager.set_setting("default_sort_order", "A - Z")

        # Ensure items_per_page and tags_per_page are set if not already present
        if not self.db_manager.get_setting("items_per_page"):
            self.db_manager.set_setting("items_per_page", "5")
        if not self.db_manager.get_setting("tags_per_page"):
            self.db_manager.set_setting("tags_per_page", "10")

        # Load items_per_page and tags_per_page from settings
        self.items_per_page = int(self.db_manager.get_setting("items_per_page", "5"))  # Default to 5
        self.tags_per_page = int(self.db_manager.get_setting("tags_per_page", "10"))  # Default to 10

        self.total_pages = 0  # Calculate based on the number of items
        self.filtered_characters = []  # This will hold the search results
        self.search_debounce_timer = None

        # Pagination variables for tags
        self.assigned_tags_current_page = 0
        self.potential_tags_current_page = 0
        # Initialize empty lists for tags
        self.assigned_tags_full_list = []
        self.potential_tags_full_list = []

        self.thumbnail_queue = queue.Queue()  # Initialize the queue
        self.process_thumbnail_queue()        # Start processing the queue

                # Initialize ExtraImagesManager
        self.extra_images_manager = ExtraImagesManager(
            self,  # Pass the main app window as master
            db_path=self.db_manager.db_path,
            get_character_name_callback=self.get_character_name,
            show_message_callback=self.show_message,
        )

        db_path=self.db_manager.db_path
        self.lorebook_manager = LorebookManager(self.settings["sillytavern_path"], db_path)
        self.selected_lorebook_id = None  # Initialize with None

        # Layout
        self.grid_columnconfigure(0, weight=1)  # Sidebar grows slightly
        self.grid_columnconfigure(1, weight=2)  # Character list grows moderately
        self.grid_columnconfigure(2, weight=5)  # Edit panel grows the most
        self.grid_rowconfigure(0, weight=1)     # Allow row to stretch vertically

        # Create UI components
        self.create_sidebar()
        self.create_character_list()
        self.create_edit_panel()

######################################################################################################
############################################# APP SETTINGS ###########################################
######################################################################################################

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
        self.db_manager.set_setting("items_per_page", updated_settings["items_per_page"])
        self.db_manager.set_setting("tags_per_page", updated_settings["tags_per_page"])

        # Apply appearance mode
        ctk.set_appearance_mode(updated_settings["appearance_mode"])

        # Refresh sort order in the character list
        self.sort_var.set(updated_settings["default_sort_order"])
        self.sort_character_list(updated_settings["default_sort_order"])

        # Reinitialize the tag manager if the SillyTavern path has changed
        if "sillytavern_path" in updated_settings:
            new_sillytavern_path = Path(updated_settings["sillytavern_path"].strip())
            if not new_sillytavern_path.exists():
                self.show_message("The updated SillyTavern path does not exist. Please check your settings.", "error")
                return

            print("Reinitializing SillyTavernTagManager with the new path...")
            self.tag_manager = SillyTavernTagManager(new_sillytavern_path)

        # Update items_per_page and tags_per_page dynamically in the UI
        self.items_per_page = int(updated_settings["items_per_page"])
        self.tags_per_page = int(updated_settings["tags_per_page"])

        # Refresh UI to reflect updated pagination settings
        self.filter_character_list()
        self.update_assigned_tags()
        self.update_potential_tags()

######################################################################################################
############################################# GUI SIDEBAR ############################################
######################################################################################################

    def create_sidebar(self):
        """Create the sidebar with menu options."""
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nswe")

        # # Sidebar Title
        # sidebar_label = ctk.CTkLabel(self.sidebar, text="Menu", font=ctk.CTkFont(size=18, weight="bold"))
        # sidebar_label.pack(pady=10)

        # Space for "Currently Selected Character"
        self.selected_character_frame = None  # Will be created when a character is selected

        # Buttons in the sidebar
        self.add_character_button = ctk.CTkButton(self.sidebar, text="Add Character", command=self.add_character)
        self.add_character_button.pack(pady=10, padx=10, fill="x")

        # self.import_button = ctk.CTkButton(self.sidebar, text="Import Cards From SillyTavern", command=self.open_import_modal)
        # self.import_button.pack(pady=10, padx=10, fill="x")

        self.sync_button = ctk.CTkButton(self.sidebar, text="Sync Data from SillyTavern", command=self.sync_cards_from_sillytavern)
        self.sync_button.pack(pady=10, padx=10, fill="x")


        self.import_button = ctk.CTkButton(self.sidebar, text="Manage Tags", command=self.open_import_tags_modal)
        self.import_button.pack(pady=10, padx=10, fill="x")

        self.manage_lorebooks_button = ctk.CTkButton(self.sidebar, text="Manage Lorebooks", command=self.open_lorebooks_modal_action)
        self.manage_lorebooks_button.pack(pady=10, padx=10, fill="x")


        # self.export_button = ctk.CTkButton(self.sidebar, text="Export Data", command=self.export_data)
        # self.export_button.pack(pady=10, padx=10, fill="x")

        self.settings_button = ctk.CTkButton(self.sidebar, text="Settings", command=self.open_settings)
        self.settings_button.pack(pady=10, padx=10, fill="x")


######################################################################################################
######################################## GUI CHARACTER LIST ##########################################
######################################################################################################

    def create_character_list(self):
        """Create the middle column for the character list."""
        self.character_list_frame = ctk.CTkFrame(self)
        self.character_list_frame.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)

        # # Title
        # list_label = ctk.CTkLabel(self.character_list_frame, text="Character List", font=ctk.CTkFont(size=14, weight="bold"))
        # list_label.pack(pady=(10, 0))

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
        
        # Create a horizontal frame for the sort dropdown and tags filter button
        sort_and_filter_frame = ctk.CTkFrame(self.character_list_frame, fg_color="transparent")
        sort_and_filter_frame.pack(fill="x", padx=10, pady=0)  # Reduce vertical padding

        # Spacer frame on the left for centering
        left_spacer = ctk.CTkFrame(sort_and_filter_frame, width=0, height=10,  fg_color="transparent")
        left_spacer.pack(side="left", expand=True)

        # Sort Dropdown
        default_sort_order = self.db_manager.get_setting("default_sort_order", "A - Z")
        self.sort_var = ctk.StringVar(value=default_sort_order)
        sort_dropdown = ctk.CTkOptionMenu(
            sort_and_filter_frame,
            values=["A - Z", "Z - A", "Newest", "Oldest", "Most Recently Edited"],
            variable=self.sort_var,
            command=self.sort_character_list,
            height=30  # Reduce height
        )
        sort_dropdown.pack(side="left", padx=(0, 10))  # Adjust padding

        # Character Tags Filter Button
        self.character_tags_filter = []
        char_tags_button = ctk.CTkButton(
            sort_and_filter_frame,
            text="Filter by Tags",
            command=lambda: self.open_tag_filter_modal("Character Tags", self.character_tags_filter),
            height=30  # Match height with dropdown
        )
        char_tags_button.pack(side="left")

        # Spacer frame on the right for centering
        right_spacer = ctk.CTkFrame(sort_and_filter_frame, width=0, height=10, fg_color="transparent")
        right_spacer.pack(side="left", expand=True)

        
        # Scrollable Frame for Characters
        self.scrollable_frame = ctk.CTkScrollableFrame(self.character_list_frame)
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # Ensure scrollbar resets to the top at initialization
        self.scrollable_frame._parent_canvas.yview_moveto(0)

        # Navigation Buttons
        self.create_navigation_buttons()

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

            # Reset scrollbar to the top
        self.scrollable_frame.update_idletasks()  # Ensure the frame is fully updated
        self.scrollable_frame._parent_canvas.yview_moveto(0)  # Scroll to the top


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
            self.scrollable_frame._parent_canvas.yview_moveto(0)

    def next_page(self):
        """Go to the next page."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_characters()
            self.update_navigation_buttons()
            self.scrollable_frame._parent_canvas.yview_moveto(0)


    def filter_character_list(self, no_tags_only=False):
        """Filter the character list based on search query and selected tags."""
        query = self.search_var.get().lower().strip()
        selected_tags = self.character_tags_filter

        def character_has_selected_tags(character_name):
            character_name_png = f"{character_name}.png" if not character_name.endswith(".png") else character_name
            character_tags = [
                self.tag_manager.get_tag_by_id(tag_id)["name"]
                for tag_id in self.tag_manager.tag_map.get(character_name_png, [])
            ]
            return all(tag in character_tags for tag in selected_tags)

        def character_has_no_tags(character_name):
            character_name_png = f"{character_name}.png" if not character_name.endswith(".png") else character_name
            return character_name_png not in self.tag_manager.tag_map or not self.tag_manager.tag_map[character_name_png]

        self.filtered_characters = [
            char for char in self.all_characters
            if (not query or query in char["name"].lower())
            and (not selected_tags or character_has_selected_tags(char["name"]))
            and (not no_tags_only or character_has_no_tags(char["name"]))
        ]

        # Recalculate pages and refresh the display
        self.total_pages = (len(self.filtered_characters) + self.items_per_page - 1) // self.items_per_page
        self.current_page = 0
        self.display_characters()
        self.update_navigation_buttons()


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
                "image_path": row[2],
                "main_file": row[2],
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
        char_frame.pack(pady=(0, 1), padx=5, fill="x")

        image_path = character.get("image_path", "assets/default_thumbnail.png")
        created_date = character.get("created_date", "Unknown Date")
        last_modified_date = character.get("last_modified_date", "Unknown Date")

        # Reformat dates for display
        formatted_created_date = self.format_date(created_date)
        formatted_last_modified_date = self.format_date(last_modified_date)

        # Layout for character frame
        char_frame.grid_columnconfigure(0, weight=0)  # Fixed size for image column
        char_frame.grid_columnconfigure(1, weight=1)  # Flexible size for text column

        # Add Placeholder Thumbnail
        placeholder_thumbnail = ctk.CTkImage(Image.open("assets/default_thumbnail.png"), size=(50, 75))
        thumbnail_label = ctk.CTkLabel(char_frame, image=placeholder_thumbnail, text="")
        thumbnail_label.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky="n")

        # Add Thumbnail with lazy loading
        thumbnail_label = ctk.CTkLabel(char_frame, text="")
        thumbnail_label.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky="n")
        self.create_thumbnail(
            image_path,
            callback=lambda widget, thumbnail: widget.configure(image=thumbnail),
            widget_ref=weakref.ref(thumbnail_label)
        )

            # Character Name Label
        name_label = ctk.CTkLabel(char_frame, text=character["name"], anchor="w", font=ctk.CTkFont(size=14, weight="bold"))
        name_label.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        # Created Date Label
        created_date_label = ctk.CTkLabel(char_frame, text=f"Created: {formatted_created_date}", anchor="w", font=ctk.CTkFont(size=12))
        created_date_label.grid(row=1, column=1, sticky="w", padx=5)

        # Last Modified Date Label
        modified_date_label = ctk.CTkLabel(char_frame, text=f"Last Modified: {formatted_last_modified_date}", anchor="w", font=ctk.CTkFont(size=12))
        modified_date_label.grid(row=2, column=1, sticky="w", pady=(0, 3), padx=5)

        # Bind click events to `select_character_by_id`
        widgets_to_bind = [char_frame, thumbnail_label, name_label, created_date_label, modified_date_label]
        for widget in widgets_to_bind:
            widget.bind("<Button-1>", lambda e, char_id=character["id"]: self.select_character_by_id(char_id))

        
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
        title_label = ctk.CTkLabel(
            self.selected_character_frame,
            text="Currently Selected Character",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title_label.pack(pady=(0, 5))

        # Add character name label with word wrap
        name_label = ctk.CTkLabel(
            self.selected_character_frame,
            text=character_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=180,  # Ensure text wraps within the sidebar width
            anchor="w",  # Align text to the left if needed
            justify="left"  # Text alignment
        )
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
        

    def clear_selected_character_sidebar(self):
        """Clear the currently selected character details from the sidebar."""
        if self.selected_character_frame:
            # Destroy all child widgets inside the selected character frame
            for widget in self.selected_character_frame.winfo_children():
                widget.destroy()

            # Hide the frame
            self.selected_character_frame.pack_forget()


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
            

    def select_character_by_id(self, character_id):
        """Handle character selection by ID and populate the edit panel."""
        try:
            # Get the currently visible tab, if any
            current_tab_name = None
            if hasattr(self, "edit_panel"):
                for widget in self.edit_panel.winfo_children():
                    if isinstance(widget, ctk.CTkTabview):
                        current_tab_name = widget.get()  # Get the name of the currently active tab
                        break

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
                self.selected_character_name = result[1]
                name, main_file, notes, misc_notes, created_date, last_modified_date = result[1:]

                # Handle None values
                notes = notes or ""
                misc_notes = misc_notes or ""

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
                            field.update_idletasks()

                # Load extra images for the selected character
                self.extra_images_manager.load_extra_images(
                    self.selected_character_id,
                    self.extra_images_frame,
                    self.create_thumbnail,
                )

                self.load_related_characters()
                self.load_tags_for_character(name)

                # Update the currently selected character in the sidebar
                image_path = (
                    Path("CharacterCards") / name / main_file
                    if main_file else Path("assets/default_thumbnail.png")
                )
                self.update_currently_selected_character(name, str(image_path))

                # Parse and load char metadata if main_file exists
                if main_file:
                    png_path = Path("CharacterCards") / name / main_file
                    if png_path.exists():
                        try:
                            metadata = PNGMetadataReader.extract_text_metadata(str(png_path))
                            highest_spec_metadata = PNGMetadataReader.get_highest_spec_fields(metadata)
                            self.load_card_data(highest_spec_metadata)  # Load into the Card Data tab
                        except Exception as e:
                            print(f"Error parsing metadata: {e}")
                            self.load_card_data({"Error": "Could not parse metadata."})
                    else:
                        self.load_card_data({"Error": "Main file not found."})
                else:
                    self.load_card_data({"Error": "No main file specified."})


                # Highlight the selected character in the list
                self.highlight_selected_character(character_id)

                # Restore the previously active tab
                if hasattr(self, "edit_panel") and current_tab_name:
                    for widget in self.edit_panel.winfo_children():
                        if isinstance(widget, ctk.CTkTabview):
                            widget.set(current_tab_name)  # Restore the active tab
                            break
            else:
                # Handle case where the character does not exist
                self.clear_edit_panel()
                self.show_message("Character not found. Please refresh the list.", "error")

        except Exception as e:
            print(f"Error in select_character_by_id: {e}")

######################################################################################################
########################################## GUI EDIT PANEL ############################################
######################################################################################################

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

        # Card Data Tab
        chardata_tab = tabview.add("Card Data")

        # Label for Card Data Display
        chardata_label = ctk.CTkLabel(
            chardata_tab,
            text="Read-Only:",
            font=ctk.CTkFont(size=10, weight="bold")
        )
        chardata_label.pack(anchor="w", padx=0, pady=0)

        # Frame to hold dynamically created fields
        self.chardata_frame = ctk.CTkScrollableFrame(chardata_tab)
        self.chardata_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Extra Images Tab
        images_tab = tabview.add("Images")
        self.add_image_button = ctk.CTkButton(
            images_tab,
            text="Add Image",
            command=self.extra_images_manager.add_image_to_character
        )
        self.add_image_button.pack(pady=5, padx=10)
        self.extra_images_frame = ctk.CTkScrollableFrame(images_tab, height=200)
        self.extra_images_frame.pack(fill="both", expand=True, padx=0, pady=5)

        # Related Characters Tab
        related_tab = tabview.add("Related")

        # Add Button for Linking a Character
        self.add_related_character_button = ctk.CTkButton(
            related_tab,
            text="Link Character",
            command=self.open_link_character_modal
        )
        self.add_related_character_button.pack(pady=2, padx=10)
        
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

        # Tags Tab
        tags_tab = tabview.add("Tags")

        # Assigned Tags Section
        assigned_tag_label = ctk.CTkLabel(
            tags_tab, text="Assigned Character Tags:", font=ctk.CTkFont(size=12, weight="bold")
        )
        assigned_tag_label.pack(pady=(2, 1), padx=5, anchor="w")

        # Wrapping frame for assigned tags
        assigned_tags_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        assigned_tags_wrapper.pack(fill="x", padx=10, pady=(0, 1))
        assigned_tags_wrapper.pack_propagate(False)

        # Assigned Tags Frame inside wrapper
        self.assigned_tags_frame = ctk.CTkScrollableFrame(assigned_tags_wrapper)
        self.assigned_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Assigned Tags Pagination
        self.assigned_tags_pagination = ctk.CTkFrame(tags_tab)
        self.assigned_tags_pagination.pack(fill="x", padx=10, pady=(0, 10))

        # Potential Tags Section
        potential_tag_label = ctk.CTkLabel(
            tags_tab, text="Available Character Tags:", font=ctk.CTkFont(size=12, weight="bold")
        )
        potential_tag_label.pack(pady=(2, 1), padx=5, anchor="w")

        # Wrapping frame for potential tags
        potential_tags_wrapper = ctk.CTkFrame(tags_tab, height=150)  # Set desired height
        potential_tags_wrapper.pack(fill="x", padx=10, pady=(0, 1))
        potential_tags_wrapper.pack_propagate(False)

        # Potential Tags Frame inside wrapper
        self.potential_tags_frame = ctk.CTkScrollableFrame(potential_tags_wrapper)
        self.potential_tags_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Potential Tags Pagination
        self.potential_tags_pagination = ctk.CTkFrame(tags_tab)
        self.potential_tags_pagination.pack(fill="x", padx=10, pady=(0, 10))

        # Initialize pagination variables
        self.tags_per_page = 10
        self.assigned_tags_current_page = 0
        self.potential_tags_current_page = 0

        # Search/Add Input for Character Tags
        self.character_tag_search_var = ctk.StringVar()
        character_tag_frame = ctk.CTkFrame(tags_tab, fg_color="transparent")
        character_tag_frame.pack(fill="x", padx=10, pady=(1, 0))

        character_tag_entry = ctk.CTkEntry(
            character_tag_frame,
            textvariable=self.character_tag_search_var,
            placeholder_text="Search or add character tags...",
            width=260,
        )
        character_tag_entry.pack(side="left", fill="x", expand=True)

        # Dropdown for sorting tags
        self.sorting_var = ctk.StringVar(value="A-Z")  # Default sorting
        sorting_frame = ctk.CTkFrame(tags_tab, fg_color="transparent")
        sorting_frame.pack(fill="x", padx=10, pady=(5, 0))

        sorting_label = ctk.CTkLabel(sorting_frame, text="Sort by:")
        sorting_label.pack(side="left", padx=5)

        sorting_dropdown = ctk.CTkOptionMenu(
            sorting_frame,
            variable=self.sorting_var,
            values=["A-Z", "Z-A"],
            command=lambda _: self.update_sorted_tags()
        )
        sorting_dropdown.pack(side="left", fill="x", expand=True, padx=5)

        # Bind search entry events
        character_tag_entry.bind(
            "<KeyRelease>",
            lambda e: self.update_tag_search_results(self.character_tag_search_var.get())
        )
        character_tag_entry.bind(
            "<Return>",
            lambda e: self.add_tag_from_input(self.character_tag_search_var, "character")
        )   

        # Add Tag Button
        character_add_tag_button = ctk.CTkButton(
            character_tag_frame,
            text="+",
            width=30,
            command=lambda: self.add_tag_from_input(self.character_tag_search_var, "character"),
        )
        character_add_tag_button.pack(side="left", padx=(5, 0))

        # Load initial data with pagination
        self.update_assigned_tags()
        self.update_potential_tags()

        # Metadata Tab
        metadata_tab = tabview.add("MetaData")

        self.main_file_label = ctk.CTkLabel(
            metadata_tab, 
            text="Main File: ", 
            wraplength=400,  # Set wraplength to control text wrapping
            anchor="w",      # Align text to the left
            justify="left"   # Ensure the text wraps properly
        )
        self.main_file_label.pack(anchor="w", padx=10, pady=5, fill="x")  # Use fill="x" to allow horizontal expansion

        self.created_date_label = ctk.CTkLabel(metadata_tab, text="Created: ")
        self.created_date_label.pack(anchor="w", padx=10, pady=5)

        self.last_modified_date_label = ctk.CTkLabel(metadata_tab, text="Last Modified: ")
        self.last_modified_date_label.pack(anchor="w", padx=10, pady=5)

        # Save Button
        self.save_button = ctk.CTkButton(self.edit_panel, text="Save Changes", command=self.save_changes)
        self.save_button.pack(pady=0, padx=10, fill="x")

        # Create a font with a specific size
        small_font = CTkFont(size=10)
        self.save_button_label = ctk.CTkLabel(
            self.edit_panel,
            text="All images, character links and tag changes will auto save. Notes and Character Name changes must be saved manually.",
            font=small_font,
            wraplength=280,
            justify="center",
        )
        self.save_button_label.pack(anchor="center", padx=10, pady=0)

        # Bind mouse wheel scrolling for main scrollable frames
        self.bind_mouse_wheel(self.scrollable_frame)  # Character list
        self.bind_mouse_wheel(self.edit_panel)  # Edit panel
        self.bind_mouse_wheel(self.extra_images_frame)  # Extra Images

        # Related Characters
        self.bind_mouse_wheel(self.related_characters_frame)

        # Tags
        self.bind_mouse_wheel(self.assigned_tags_frame)
        self.bind_mouse_wheel(self.potential_tags_frame)

        # Automatically select the first character if none is selected
        if not hasattr(self, "selected_character_id") and self.filtered_characters:
            first_character_id = self.filtered_characters[0]["id"]
            self.select_character_by_id(first_character_id)


    def load_extra_images(self):
        """Delegate to ExtraImagesManager."""
        self.extra_images_manager.load_extra_images(
            self.selected_character_id,
            self.extra_images_frame,
            self.create_thumbnail
        )


    def load_card_data(self, card_data):
        """
        Dynamically create labels and textboxes for each key in the card data, with custom heights for specific keys.
        """
        # Define custom heights for specific keys
        custom_heights = {
            "name": 20,
            "description": 150,
            "personality": 150,
            "scenario": 150,
            "first_mes": 150,
            "mes_example": 150,
            "creator_notes": 100,
            "creator": 20,
            "creatorcomment": 50,
            "character_version": 20,
            "extensions": 50,
            "alternate_greetings": 100,
            "group_only_greetings": 50,
            "tags": 100,
        }
        default_height = 50  # Default height for unspecified keys

        # Clear previous fields
        for widget in self.chardata_frame.winfo_children():
            widget.destroy()

        # Create a field for each key-value pair in the card data
        for key, value in card_data.items():
            # Label for the key
            key_label = ctk.CTkLabel(
                self.chardata_frame,
                text=f"{key}:",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            key_label.pack(anchor="w", padx=0, pady=0)

            # Determine the height of the textbox
            height = custom_heights.get(key, default_height)

            # Read-only textbox for the value
            value_text = ctk.CTkTextbox(self.chardata_frame, height=height, state="normal", wrap="word")
            value_text.insert("1.0", json.dumps(value, indent=4) if isinstance(value, (dict, list)) else str(value))
            value_text.configure(state="disabled")  # Make the textbox read-only
            value_text.pack(fill="x", padx=0, pady=(0, 2))


    def display_character_metadata(self, character_metadata):
        """
        Display the character's metadata in the Metadata tab.
        """
        self.load_card_data(character_metadata)


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


######################################################################################################
########################################### DELETE CHARACTER #########################################
######################################################################################################

    def confirm_delete_character(self):
        """Show a confirmation prompt before deleting a character."""
        if not hasattr(self, "selected_character_id"):
            self.show_message("No character selected to delete.", "error")
            return


        confirm = askyesno(
            title="Delete Character",
            message="Are you sure you want to delete this character? THIS ALSO DELETES THE CHARACTER IN SILLYTAVERN. This action cannot be undone.",
        )
        if confirm:
            self.delete_character()

    def delete_character(self):
        """Delete the selected character from the database, app folder, and SillyTavern."""
        try:
            # Ensure we have a valid character ID
            if not hasattr(self, "selected_character_id"):
                raise ValueError("No character selected for deletion.")

            print(f"Deleting character ID: {self.selected_character_id}")

            # Get character name and main file from the database
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT name, main_file FROM characters WHERE id = ?",
                (self.selected_character_id,)
            )
            result = cursor.fetchone()
            connection.close()

            if not result:
                self.show_message("Character not found in the database.", "error")
                return

            character_name, main_file = result

            # Paths
            app_folder_path = Path("CharacterCards") / character_name
            sillytavern_file_path = Path(self.settings["sillytavern_path"]).resolve() / "characters" / main_file

            # Delete the app folder
            if app_folder_path.exists():
                shutil.rmtree(app_folder_path)
                print(f"Deleted app folder: {app_folder_path}")
            else:
                print(f"App folder not found: {app_folder_path}")

            # Delete the PNG file in SillyTavern
            if sillytavern_file_path.exists():
                sillytavern_file_path.unlink()
                print(f"Deleted file in SillyTavern: {sillytavern_file_path}")
            else:
                print(f"File not found in SillyTavern: {sillytavern_file_path}")

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


######################################################################################################
############################################## ADD CHARACTER #########################################
######################################################################################################

    def add_character(self):
        """Open a new window to add a character."""
        # Create the modal window using CTkToplevel
        self.add_character_window = ctk.CTkToplevel(self)
        self.add_character_window.title("Add Character")
        self.add_character_window.geometry("400x350")

        # Ensure the modal stays on top of the main window
        self.add_character_window.transient(self)  # Set to be a child of the main window
        self.add_character_window.grab_set()       # Block interaction with the main window

            # Add a protocol handler for the window close event
        self.add_character_window.protocol("WM_DELETE_WINDOW", self.cleanup_temp_imported_file)

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

        browse_button = ctk.CTkButton(file_frame, text="Browse", width=100, command=self.browse_file_add_char)
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

    def import_aicc_card(self):
        """Import a card from AICC and handle only the file import."""
        card_id = self.card_id_entry.get().strip()
        if not card_id:
            self.show_add_character_message("Please enter a valid Card ID.", "error")
            return

        try:
            # Use SillyTavern path as the download target directory
            sillytavern_path = Path(self.settings["sillytavern_path"]).resolve() / "characters"

            # Parse the card ID to get the file name
            parts = card_id.split("/")
            if len(parts) != 3 or parts[0] != "AICC":
                raise ValueError("Invalid card ID format. Expected 'AICC/author/title'.")
            title = parts[2]  # Extract the title as the file name
            target_file_path = sillytavern_path / f"{title}.png"

            # Check if the file already exists
            if target_file_path.exists():
                response = askyesno(
                    "File Conflict",
                    "The file already exists in your SillyTavern folder. Do you want to create a new copy?"
                )
                if response:
                    base_name = target_file_path.stem
                    extension = target_file_path.suffix
                    counter = 1
                    while target_file_path.exists():
                        target_file_path = sillytavern_path / f"{base_name}_{counter}{extension}"
                        counter += 1
                else:
                    self.show_add_character_message("Import canceled due to name conflict.", "error")
                    return

            # Fetch the card details and download the PNG file
            card_details, downloaded_file = AICCImporter.fetch_card(card_id, target_file_path)

            # Extract details from the API response
            card_name = card_details.get("title", None)
            excerpt = card_details.get("excerpt", "").strip()
            content = card_details.get("content", "").strip()

            # Attempt to read metadata from the file for fallback
            try:
                metadata = PNGMetadataReader.extract_text_metadata(str(downloaded_file))
                highest_spec_metadata = PNGMetadataReader.get_highest_spec_fields(metadata)
                creator_notes = highest_spec_metadata.get("creator_notes", "").strip()
                description = highest_spec_metadata.get("description", "").strip()
            except Exception as e:
                print(f"Error reading metadata: {e}")
                creator_notes = ""
                description = ""

            # Define the unwanted text
            unwanted_notes = (
                "This card was uploaded to https://aicharactercards.com, "
                "please come back and rate the card if you enjoy it to help other users find the card."
            )
            if creator_notes == unwanted_notes:
                creator_notes = ""
            elif unwanted_notes in creator_notes:
                creator_notes = creator_notes.replace(unwanted_notes, "").strip()

            # Populate the file path and name fields
            self.file_path_entry.delete(0, "end")
            self.file_path_entry.insert(0, str(downloaded_file))

            if card_name:
                self.add_character_name_entry.delete(0, "end")
                self.add_character_name_entry.insert(0, card_name)
            else:
                formatted_name = " ".join(word.capitalize() for word in title.replace("_", " ").replace("-", " ").split())
                self.add_character_name_entry.delete(0, "end")
                self.add_character_name_entry.insert(0, formatted_name)

            # Prioritize notes: excerpt > content > creator_notes > description
            if excerpt:
                notes = excerpt
            elif content:
                notes = content
            elif creator_notes:
                notes = creator_notes
            elif description:
                notes = self.truncate_to_100_words(description)
            else:
                notes = ""

            self.add_character_notes_textbox.delete("1.0", "end")
            self.add_character_notes_textbox.insert("1.0", notes)

            # Set the flag to indicate the file was imported
            self.is_imported_flag = True

            self.show_add_character_message("Card imported successfully. Fill in other details before saving.", "success")

        except Exception as e:
            self.show_add_character_message(f"Error importing card: {str(e)}", "error")


    def cleanup_temp_imported_file(self):
        """Cleanup the temporary imported file if it exists and close the modal."""
        if hasattr(self, "temp_imported_file") and self.temp_imported_file:
            try:
                temp_file = Path(self.temp_imported_file)
                if temp_file.exists():
                    temp_file.unlink()  # Delete the file
                    print(f"Temporary file {temp_file} deleted.")
            except Exception as e:
                print(f"Error cleaning up temporary file: {e}")
            finally:
                self.temp_imported_file = None  # Reset the attribute

        # Destroy the modal window
        self.add_character_window.destroy()



######################################################################################################
######################################## Add Characters  #############################################
######################################################################################################

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

    def browse_file_add_char(self):
        """Open a file dialog to select an image or JSON file."""
        file_path = askopenfilename(filetypes=[("Image/JSON Files", "*.png *.jpg *.jpeg *.json")])
        if file_path:
            # Update file path entry
            self.file_path_entry.delete(0, "end")
            self.file_path_entry.insert(0, file_path)

            # Attempt to read metadata from the file
            try:
                if file_path.endswith(".png"):  # Only parse PNG files for metadata
                    metadata = PNGMetadataReader.extract_text_metadata(file_path)
                    highest_spec_metadata = PNGMetadataReader.get_highest_spec_fields(metadata)
                    card_name = highest_spec_metadata.get("name", None)  # Extract the 'name' field
                    creator_notes = highest_spec_metadata.get("creator_notes", "").strip()
                    description = highest_spec_metadata.get("description", "").strip()
                else:
                    card_name = None
                    creator_notes = ""
                    description = ""
            except Exception as e:
                print(f"Error reading metadata: {e}")
                card_name = None
                creator_notes = ""
                description = ""

            # Default character name to the 'name' from metadata or formatted file name
            if card_name:
                default_name = card_name
            else:
                default_name = Path(file_path).stem
                default_name = " ".join(word.capitalize() for word in default_name.replace("_", " ").replace("-", " ").split())

            self.add_character_name_entry.delete(0, "end")
            self.add_character_name_entry.insert(0, default_name)

            # Skip unwanted creator_notes text
            unwanted_notes = (
                "This card was uploaded to https://aicharactercards.com, "
                "please come back and rate the card if you enjoy it to help other users find the card."
            )
            if creator_notes == unwanted_notes:
                creator_notes = ""  # Treat it as empty
            elif unwanted_notes in creator_notes:
                # Remove unwanted text if other content exists
                creator_notes = creator_notes.replace(unwanted_notes, "").strip()

            # Populate character notes
            if creator_notes:
                notes = creator_notes
            elif description:
                notes = self.truncate_to_100_words(description)
            else:
                notes = ""

            self.add_character_notes_textbox.delete("1.0", "end")
            self.add_character_notes_textbox.insert("1.0", notes)




######################################################################################################
############################### Sync Data from SillyTavern ###########################################
######################################################################################################

    def sync_cards_from_sillytavern(self):
        """Sync cards from SillyTavern."""
        try:
            # Create a modal for progress feedback
            self.sync_modal = ctk.CTkToplevel(self)
            self.sync_modal.title("Syncing Cards")
            self.sync_modal.geometry("300x200")
            self.sync_modal.transient(self)
            self.sync_modal.grab_set()

            # Progress Label
            progress_label = ctk.CTkLabel(self.sync_modal, text="Syncing cards, please wait...")
            progress_label.pack(pady=(20, 10), padx=10)

            # Progress Bar
            progress_var = ctk.DoubleVar()
            progress_bar = ctk.CTkProgressBar(self.sync_modal, variable=progress_var, width=250)
            progress_bar.pack(pady=10, padx=10)
            progress_bar.set(0)

            # Batch Progress Label
            batch_progress_label = ctk.CTkLabel(self.sync_modal, text="Processed: 0/0")
            batch_progress_label.pack(pady=(5, 10), padx=10)

            # Function to perform sync in the background
            def perform_sync():
                try:
                    # Normalize paths
                    def sanitize_path(path: str):
                        return Path(path).resolve()

                    characters_path = sanitize_path(self.settings["sillytavern_path"]) / "characters"
                    app_characters_path = Path("CharacterCards").resolve()

                    if not characters_path.exists():
                        self.show_message("SillyTavern path not configured or does not exist. Set it in Settings.", "error")
                        return

                    app_characters_path.mkdir(parents=True, exist_ok=True)

                    new_characters_added = False

                    png_files = list(characters_path.glob("*.png"))
                    total_files = len(png_files)

                    for idx, png_file in enumerate(png_files, start=1):
                        character_name = png_file.stem
                        character_folder = app_characters_path / character_name

                        # Ensure character folder exists
                        character_folder.mkdir(parents=True, exist_ok=True)

                        # Skip cards that already exist in the database
                        with sqlite3.connect(self.db_manager.db_path) as connection:
                            cursor = connection.cursor()
                            cursor.execute("SELECT id FROM characters WHERE main_file = ?", (str(png_file),))
                            if cursor.fetchone():
                                continue

                        # Extract metadata
                        try:
                            metadata = PNGMetadataReader.extract_text_metadata(str(png_file))
                            highest_spec_metadata = PNGMetadataReader.get_highest_spec_fields(metadata)
                            new_name = highest_spec_metadata.get("name", character_name)
                            new_notes = highest_spec_metadata.get("creator_notes", "").strip()
                            description = highest_spec_metadata.get("description", "").strip()

                            # Process notes
                            unwanted_notes = (
                                "This card was uploaded to https://aicharactercards.com, "
                                "please come back and rate the card if you enjoy it to help other users find the card."
                            )
                            if new_notes == unwanted_notes:
                                new_notes = ""
                            elif unwanted_notes in new_notes:
                                new_notes = new_notes.replace(unwanted_notes, "").strip()

                            if not new_notes and description:
                                new_notes = self.truncate_to_100_words(description)

                        except Exception as e:
                            print(f"Error reading metadata for {png_file}: {e}")
                            new_name = character_name
                            new_notes = ""

                        # Get file creation and modification dates
                        file_stat = os.stat(png_file)
                        created_date = datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                        last_modified_date = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                        # Add new character to database
                        with sqlite3.connect(self.db_manager.db_path) as connection:
                            cursor = connection.cursor()
                            cursor.execute(
                                """
                                INSERT INTO characters (name, main_file, notes, created_date, last_modified_date) 
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (new_name, str(png_file), new_notes, created_date, last_modified_date),
                            )
                            connection.commit()
                            new_characters_added = True

                        # Update progress bar safely
                        try:
                            if progress_bar.winfo_exists():
                                progress_var.set(idx / total_files)
                                progress_bar.update_idletasks()
                        except Exception as e:
                            print(f"Error updating progress bar: {e}")

                        # Update batch progress label safely
                        try:
                            if batch_progress_label.winfo_exists():
                                if idx % 10 == 0 or idx == total_files:
                                    batch_progress_label.configure(text=f"Processed: {idx}/{total_files}")
                                    batch_progress_label.update_idletasks()
                        except Exception as e:
                            print(f"Error updating batch progress label: {e}")

            # Sync lorebooks
                    print("Starting lorebook synchronization...")
                    try:
                        lorebook_manager = LorebookManager(self.settings["sillytavern_path"], self.db_manager.db_path)
                        lorebook_manager.sync_lorebooks()
                        print("Lorebook synchronization completed.")
                    except Exception as e:
                        print(f"Error during lorebook sync: {e}")
                        self.show_message("Failed to sync lorebooks. Check logs for details.", "error")

                    # Refresh tags after sync
                    self.refresh_tags_after_sync()
                    self.show_message("Sync completed successfully!", "success")

                except Exception as e:
                    print(f"Error during sync: {e}")
                    self.show_message(f"Failed to sync cards: {e}", "error")
                finally:
                    # Ensure modal still exists before destroying it
                    if self.sync_modal and self.sync_modal.winfo_exists():
                        self.sync_modal.destroy()

            # Run the sync in a background thread to keep the UI responsive
            threading.Thread(target=perform_sync, daemon=True).start()

        except Exception as e:
            print(f"Error initializing sync: {e}")
            self.show_message(f"Failed to start sync: {e}", "error")


    def refresh_tags_after_sync(self):
        """Refresh tags specifically after syncing new characters from SillyTavern."""
        try:
            print("Starting refresh of tags after sync...")

            # Reload the tag manager to ensure we have the latest tag data
            self.tag_manager.reload_tags()
            print("After reload tags...")

            # Refresh the character list from the database
            self.all_characters = self.get_character_list()
            self.filtered_characters = self.all_characters.copy()  # Reset filtered characters

            # Update tag associations for all characters
            for character in self.all_characters:
                main_file_path = character.get("main_file", "")
                if not main_file_path:
                    print(f"Character {character['name']} does not have a main_file entry. Skipping.")
                    continue

                character_name_png = Path(main_file_path).name  # Extract the filename from the path
                normalized_name = self.tag_manager.normalize_filename(character_name_png)

                # Debugging output
                if normalized_name not in self.tag_manager.tag_map:
                    print(f"Character {character_name_png} not found in tag_map after normalization.")
                    continue

                associated_tags = [
                    tag["name"]
                    for tag_id in self.tag_manager.tag_map.get(normalized_name, [])
                    for tag in self.tag_manager.tags if tag["id"] == tag_id
                ]
                character["tags"] = associated_tags  # Update character tags in memory
                # print(f"Character: {character['name']}, Tags: {associated_tags}")  # Debug

            # Refresh the UI to reflect tag updates
            self.display_characters()  # Update the character display
            self.update_navigation_buttons()  # Update navigation buttons if needed
            self.update_idletasks()  # Force UI update
            print("Tags successfully reloaded and UI refreshed.")
            self.show_message("Tags refreshed successfully after sync.", "success")

        except Exception as e:
            self.show_message(f"Error refreshing tags after sync: {str(e)}", "error")
            print(f"Error refreshing tags after sync: {str(e)}", "error")

######################################################################################################
################################### Related Character Linking ########################################
######################################################################################################

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
            thumbnail = self.create_thumbnail_small(char["image_path"])
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
                "image_path": str(Path("CharacterCards") / row[1] / row[2])
            }
            for row in rows
        ]

        # Display the related characters
        self.display_related_characters()

    def open_link_character_modal(self):
        """Open a modal to search and link a new character."""
        self.link_character_window = ctk.CTkToplevel(self)
        self.link_character_window.title("Link Character")
        self.link_character_window.geometry("400x400")
            # Ensure the modal stays on top of the main window
        self.link_character_window.transient(self)  # Make modal a child of the main window
        self.link_character_window.grab_set()       # Prevent interaction with the main window
        self.link_character_window.focus_set()      # Set focus to the modal

        # Align the modal relative to the parent window
        self._align_modal_top_left(self.link_character_window)

        # Search Bar
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(self.link_character_window, textvariable=search_var, placeholder_text="Search characters...", width=300)
        search_entry.pack(pady=(10, 5), padx=10)

        # Scrollable Frame for Character List
        scrollable_frame = ctk.CTkScrollableFrame(self.link_character_window, height=300)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Pagination Controls
        nav_frame = ctk.CTkFrame(self.link_character_window)
        nav_frame.pack(fill="x", pady=(5, 10))

        prev_button = ctk.CTkButton(nav_frame, text="Previous", command=lambda: navigate_page(-1))
        prev_button.pack(side="left", padx=5)

        next_button = ctk.CTkButton(nav_frame, text="Next", command=lambda: navigate_page(1))
        next_button.pack(side="right", padx=5)

        page_label = ctk.CTkLabel(nav_frame, text="Page 1")
        page_label.pack(side="left", padx=5)

        # Cached Character List and Pagination
        all_characters = self.get_character_list()
        filtered_characters = [char for char in all_characters if char["id"] != self.selected_character_id]
        items_per_page = 20
        current_page = [0]  # Use a mutable object to allow nested functions to update the value

        def update_modal_display():
            """Update the modal with the filtered and paginated character list."""
            nonlocal filtered_characters

            # Clear existing widgets
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            # Paginate the filtered characters
            start_idx = current_page[0] * items_per_page
            end_idx = min(start_idx + items_per_page, len(filtered_characters))
            page_characters = filtered_characters[start_idx:end_idx]

            # Display characters
            for char in page_characters:
                char_frame = ctk.CTkFrame(scrollable_frame, corner_radius=5)
                char_frame.grid_columnconfigure(0, weight=0)  # Thumbnail column
                char_frame.grid_columnconfigure(1, weight=1)  # Name column
                char_frame.grid_columnconfigure(2, weight=0)  # Link button column
                char_frame.pack(pady=5, padx=5, fill="x")

                # Thumbnail
                thumbnail = self.create_thumbnail(char["image_path"])
                thumbnail_label = ctk.CTkLabel(char_frame, image=thumbnail, text="")
                thumbnail_label.image = thumbnail  # Prevent garbage collection
                thumbnail_label.grid(row=0, column=0, padx=5, sticky="w")

                # Character Name
                name_label = ctk.CTkLabel(char_frame, text=char["name"], anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
                name_label.grid(row=0, column=1, padx=5, sticky="w")

                # Link Button
                link_button = ctk.CTkButton(
                    char_frame,
                    text="Link",
                    command=lambda char_id=char["id"]: self.link_character(char_id, self.link_character_window),
                )
                link_button.grid(row=0, column=2, padx=5, sticky="e")


            # Update page label
            page_label.configure(text=f"Page {current_page[0] + 1} of {len(filtered_characters) // items_per_page + 1}")
                # Reset scrollbar to top
            scrollable_frame._parent_canvas.yview_moveto(0)  # Reset to the top

        def navigate_page(direction):
            """Navigate between pages."""
            total_pages = (len(filtered_characters) + items_per_page - 1) // items_per_page
            if 0 <= current_page[0] + direction < total_pages:
                current_page[0] += direction
                update_modal_display()

        def filter_characters(*args):
            """Filter characters based on the search query."""
            query = search_var.get().lower().strip()
            nonlocal filtered_characters
            filtered_characters = [
                char for char in all_characters if char["id"] != self.selected_character_id and query in char["name"].lower()
            ]
            current_page[0] = 0  # Reset to the first page
            update_modal_display()

        # Bind the search bar to the filter function
        search_var.trace_add("write", filter_characters)

        # Display the initial character list
        update_modal_display()

        # Mouse wheel scrolling
        self.bind_mouse_wheel(scrollable_frame)

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

######################################################################################################
#################################### Manage Tags #####################################################
######################################################################################################
    def open_import_tags_modal(self):
        """Open the modal to manage SillyTavern tags."""
        def refresh_tags_callback():
            self.refresh_tags_for_all_characters()

        tags_manager = TagsManager(
            self,
            self.db_manager.get_setting("sillytavern_path", ""),
            on_tags_updated=refresh_tags_callback
        )
        tags_manager.open()

    def load_tags_for_character(self, character_name):
        """Load tags for the selected character and apply default sorting."""
        self.tag_manager.reload_tags()

        if not character_name:
            self.clear_tags()
            return

        character_name = f"{character_name}.png" if not character_name.endswith(".png") else character_name
        character_tag_ids = self.tag_manager.tag_map.get(character_name, [])
        self.assigned_tags_full_list = [
            tag["name"] for tag in self.tag_manager.tags if tag["id"] in character_tag_ids
        ]
        self.potential_tags_full_list = [
            tag["name"] for tag in self.tag_manager.tags if tag["name"] not in self.assigned_tags_full_list
        ]

        # Apply default A-Z sorting
        self.assigned_tags_full_list.sort()
        self.potential_tags_full_list.sort()

        # Display initial tags
        self.update_assigned_tags()
        self.update_potential_tags()


    def refresh_tags_for_all_characters(self):
        """Refresh tags for all characters and update the UI."""
        try:
            print("Refreshing tags for all characters...")
            self.tag_manager.reload_tags()  # Reload the tag data
            self.clear_tags()  # Clear existing tags in the UI
            self.display_characters()  # Refresh the character list
            self.update_navigation_buttons()  # Update navigation buttons
            # Reload the currently selected character (if any)
            if hasattr(self, "selected_character_id") and self.selected_character_id:
                self.select_character_by_id(self.selected_character_id)  # Re-select the character
            self.show_message("Tags refreshed for all characters.", "success")
        except Exception as e:
            self.show_message(f"Error refreshing tags: {str(e)}", "error")

    def open_tag_filter_modal(self, title, filter_list):
        """Open a multi-select modal for tag filtering."""
        all_tags = self.get_associated_tags()  # Get tags with counts
        filtered_tags = all_tags.copy()  # Copy for filtering
        sort_options = ["A - Z", "Z - A", "Highest Count", "Lowest Count"]

        # Function to sort tags
        def sort_tags(order):
            nonlocal filtered_tags
            if order == "A - Z":
                filtered_tags.sort(key=lambda x: x[0].lower())  # Sort alphabetically
            elif order == "Z - A":
                filtered_tags.sort(key=lambda x: x[0].lower(), reverse=True)  # Reverse alphabetical
            elif order == "Highest Count":
                filtered_tags.sort(key=lambda x: x[1], reverse=True)  # Sort by count descending
            elif order == "Lowest Count":
                filtered_tags.sort(key=lambda x: x[1])  # Sort by count ascending
            update_modal_display()

        # Function to filter tags
        def filter_tags(query):
            nonlocal filtered_tags
            query = query.lower().strip()
            filtered_tags = [
                (tag, count) for tag, count in all_tags if query in tag.lower()
            ]
            update_modal_display()

        # Update the modal display
        def update_modal_display():
            # Clear existing widgets
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            for tag, count in filtered_tags:
                text = f"{tag} ({count})"
                var = tag_vars.get(tag, ctk.BooleanVar(value=tag in filter_list))
                checkbox = ctk.CTkCheckBox(scrollable_frame, text=text, variable=var)
                checkbox.pack(anchor="w", padx=10, pady=5)
                tag_vars[tag] = var

        # Modal Setup
        modal = ctk.CTkToplevel(self)
        modal.title(title)
        modal.geometry("400x500")
        modal.transient(self)
        modal.grab_set()

        # Header Frame
        header_frame = ctk.CTkFrame(modal)
        header_frame.pack(fill="x", padx=10, pady=5)

        # No Tags Assigned Checkbox
        no_tags_var = ctk.BooleanVar(value=False)
        no_tags_checkbox = ctk.CTkCheckBox(
            header_frame, text="No Tags Assigned", variable=no_tags_var
        )
        no_tags_checkbox.pack(side="left", padx=5)

        # Sort Dropdown
        sort_var = ctk.StringVar(value="A - Z")
        sort_dropdown = ctk.CTkOptionMenu(
            header_frame, values=sort_options, variable=sort_var, command=sort_tags
        )
        sort_dropdown.pack(side="left", padx=5)

        # Search Entry
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            header_frame, textvariable=search_var, placeholder_text="Search tags..."
        )
        search_entry.pack(side="left", padx=5, fill="x", expand=True)
        search_var.trace_add("write", lambda *args: filter_tags(search_var.get()))

        # Scrollable Frame
        scrollable_frame = ctk.CTkScrollableFrame(modal)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Save Button
        save_button = ctk.CTkButton(
            modal,
            text="Save",
            command=lambda: self.apply_tag_filter(
                {tag for tag, var in tag_vars.items() if var.get()},
                no_tags_var.get(),
            ),
        )
        save_button.pack(pady=10)

        # Initialize Tag Variables
        tag_vars = {}
        update_modal_display()  # Initial display
        
    def get_associated_tags(self):
        """Get tags with their associated character counts, sorted A-Z by default."""
        self.tag_manager.reload_tags()
        tags_with_counts = [
            (tag["name"], sum(tag["id"] in ids for ids in self.tag_manager.tag_map.values()))
            for tag in self.tag_manager.tags
        ]
        # Sort alphabetically by tag name
        tags_with_counts.sort(key=lambda x: x[0].lower())
        return tags_with_counts


    def apply_tag_filter(self, selected_tags, no_tags_only):
        """Apply the selected tags as filters."""
        self.character_tags_filter = selected_tags
        self.filter_character_list(no_tags_only)


    def search_tags(self, query):
        """Search globally available tags."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name FROM tags WHERE name LIKE ?
        """, (f"%{query}%"))
        tags = [row[0] for row in cursor.fetchall()]

        connection.close()
        return tags
    
    def update_sorted_tags(self):
        """Update the sorting of assigned and potential tags based on the dropdown selection."""
        sort_order = self.sorting_var.get()

        # Sort the full lists based on the selected order
        if sort_order == "A-Z":
            self.assigned_tags_full_list.sort()
            self.potential_tags_full_list.sort()
        elif sort_order == "Z-A":
            self.assigned_tags_full_list.sort(reverse=True)
            self.potential_tags_full_list.sort(reverse=True)

        # Refresh the tag displays
        self.update_assigned_tags()
        self.update_potential_tags()


    def update_assigned_tags(self):
        """Update the assigned tags display with pagination."""
        for widget in self.assigned_tags_frame.winfo_children():
            widget.destroy()

        # Get tags for the current page
        start = self.assigned_tags_current_page * self.tags_per_page
        end = start + self.tags_per_page
        visible_tags = self.assigned_tags_full_list[start:end]

        # Display tags for the current page
        for tag in visible_tags:
            tag_frame = ctk.CTkFrame(self.assigned_tags_frame, corner_radius=5)
            tag_frame.pack(pady=2, padx=5, fill="x")

            tag_label = ctk.CTkLabel(tag_frame, text=tag, anchor="w")
            tag_label.pack(side="left", padx=5)

            # Add a remove button
            remove_button = ctk.CTkButton(
                tag_frame,
                text="X",
                fg_color="red",
                width=30,
                command=lambda tag=tag: self.remove_tag_and_refresh(tag, self.selected_character_name)
            )
            remove_button.pack(side="right", padx=5)

        # Reset scroll position to top
        self.assigned_tags_frame._parent_canvas.yview_moveto(0)

        # Update pagination controls
        self.update_assigned_tags_pagination(len(self.assigned_tags_full_list))


    def update_assigned_tags_pagination(self, total_tags):
        """Update pagination controls for assigned tags."""
        for widget in self.assigned_tags_pagination.winfo_children():
            widget.destroy()

        total_pages = (total_tags + self.tags_per_page - 1) // self.tags_per_page

        prev_button = ctk.CTkButton(
            self.assigned_tags_pagination,
            text="Previous",
            state="normal" if self.assigned_tags_current_page > 0 else "disabled",
            command=lambda: self.change_assigned_tags_page(-1)
        )
        prev_button.pack(side="left", padx=5)

        page_label = ctk.CTkLabel(
            self.assigned_tags_pagination,
            text=f"Page {self.assigned_tags_current_page + 1} of {total_pages}"
        )
        page_label.pack(side="left", padx=5)

        next_button = ctk.CTkButton(
            self.assigned_tags_pagination,
            text="Next",
            state="normal" if self.assigned_tags_current_page < total_pages - 1 else "disabled",
            command=lambda: self.change_assigned_tags_page(1)
        )
        next_button.pack(side="left", padx=5)


    def update_potential_tags(self):
        """Update the potential tags display with pagination."""
        for widget in self.potential_tags_frame.winfo_children():
            widget.destroy()

        # Get tags for the current page
        start = self.potential_tags_current_page * self.tags_per_page
        end = start + self.tags_per_page
        visible_tags = self.potential_tags_full_list[start:end]

        # Display tags for the current page
        for tag in visible_tags:
            tag_frame = ctk.CTkFrame(self.potential_tags_frame, corner_radius=5)
            tag_frame.pack(pady=2, padx=5, fill="x")

            tag_label = ctk.CTkLabel(tag_frame, text=tag, anchor="w")
            tag_label.pack(side="left", padx=5)

            # Add an assign button
            add_button = ctk.CTkButton(
                tag_frame,
                text="+",
                fg_color="green",
                width=30,
                command=lambda tag=tag: self.assign_tag_to_character(tag)
            )
            add_button.pack(side="right", padx=5)

        # Reset scroll position to top
        self.potential_tags_frame._parent_canvas.yview_moveto(0)

        # Update pagination controls
        self.update_potential_tags_pagination(len(self.potential_tags_full_list))
        
    def update_potential_tags_pagination(self, total_tags):
        """Update pagination controls for potential tags."""
        for widget in self.potential_tags_pagination.winfo_children():
            widget.destroy()

        total_pages = (total_tags + self.tags_per_page - 1) // self.tags_per_page

        prev_button = ctk.CTkButton(
            self.potential_tags_pagination,
            text="Previous",
            state="normal" if self.potential_tags_current_page > 0 else "disabled",
            command=lambda: self.change_potential_tags_page(-1)
        )
        prev_button.pack(side="left", padx=5)

        page_label = ctk.CTkLabel(
            self.potential_tags_pagination,
            text=f"Page {self.potential_tags_current_page + 1} of {total_pages}"
        )
        page_label.pack(side="left", padx=5)

        next_button = ctk.CTkButton(
            self.potential_tags_pagination,
            text="Next",
            state="normal" if self.potential_tags_current_page < total_pages - 1 else "disabled",
            command=lambda: self.change_potential_tags_page(1)
        )
        next_button.pack(side="left", padx=5)


    def change_potential_tags_page(self, direction):
        """Change the current page of potential tags."""
        self.potential_tags_current_page += direction
        self.update_potential_tags()


    def change_assigned_tags_page(self, direction):
        """Change the current page of assigned tags."""
        self.assigned_tags_current_page += direction
        self.update_assigned_tags()


    def update_tag_search_results(self, query=None, event=None):
        """Update potential tag search results dynamically and reset pagination."""
        # If called by an event, extract the query from the entry widget
        if event:
            query = self.character_tag_search_var.get()

        # Fetch all tags from the tag manager
        all_tags = sorted([tag["name"] for tag in self.tag_manager.tags])

        # Get assigned tags for the selected character
        assigned_tags = set()
        if hasattr(self, "selected_character_name"):
            character_name_png = f"{self.selected_character_name}.png" if not self.selected_character_name.endswith(".png") else self.selected_character_name
            assigned_tag_ids = self.tag_manager.tag_map.get(character_name_png, [])
            assigned_tags = {
                tag["name"] for tag in self.tag_manager.tags if tag["id"] in assigned_tag_ids
            }

        # Filter tags based on the search query and exclude assigned tags
        if query and query.strip():
            filtered_tags = [
                tag for tag in all_tags if query.strip().lower() in tag.lower() and tag not in assigned_tags
            ]
        else:
            filtered_tags = [tag for tag in all_tags if tag not in assigned_tags]

        # Update the full list and reset pagination
        self.potential_tags_full_list = filtered_tags
        self.potential_tags_current_page = 0

        # Refresh the tags display
        self.update_potential_tags()

        # Reset scroll position to the top
        self.potential_tags_frame._parent_canvas.yview_moveto(0)

    def assign_tag_to_character(self, tag):
        """Assign a tag to the selected character."""
        if not hasattr(self, "selected_character_name") or not self.selected_character_name:
            self.show_message("No character selected to assign the tag.", "error")
            return

        try:
            character_name = self.selected_character_name
            if not character_name.endswith(".png"):
                character_name = f"{character_name}.png"

            self.tag_manager.assign_tag(tag, character_name)
            self.tag_manager.save_tags()

            # Refresh assigned and potential tags
            self.load_tags_for_character(self.selected_character_name)
            self.show_message(f"Tag '{tag}' assigned successfully.", "success")

        except Exception as e:
            self.show_message(f"Failed to assign tag: {str(e)}", "error")

    def add_tag_from_input(self, tag_var, tag_type):
        """Add a new tag based on user input, checking for case-insensitive duplicates."""
        tag_name = tag_var.get().strip()
        if not tag_name:
            self.show_message("Tag name cannot be empty.", "error")
            return

        try:
            # Check if the tag already exists (case-insensitive)
            existing_tag = next(
                (tag for tag in self.tag_manager.tags if tag["name"].lower() == tag_name.lower()), 
                None
            )

            if existing_tag:
                if existing_tag["name"] != tag_name:
                    # Warn the user about the capitalization mismatch
                    proceed = askyesno(
                        title="Duplicate Tag",
                        message=f"The tag '{existing_tag['name']}' already exists with different capitalization.\n"
                                f"Do you still want to create a new tag '{tag_name}'?"
                    )
                    if not proceed:
                        self.show_message("Tag creation canceled by user.", "info")
                        tag_var.set("")  # Clear the input field
                        return

            # Add the tag using the tag manager
            self.tag_manager.add_tag(tag_name)
            self.tag_manager.save_tags()

            # Automatically assign the new tag to the selected character
            if hasattr(self, "selected_character_name") and self.selected_character_name:
                character_name = self.selected_character_name
                if not character_name.endswith(".png"):
                    character_name = f"{character_name}.png"

                self.tag_manager.assign_tag(tag_name, character_name)
                self.tag_manager.save_tags()

                # Refresh assigned and potential tags
                self.load_tags_for_character(self.selected_character_name)
                self.show_message(f"Tag '{tag_name}' added and assigned to '{self.selected_character_name}' successfully.", "success")

            else:
                self.show_message("No character selected to assign the tag.", "error")

            # Clear the input field and reset the search
            tag_var.set("")
            self.update_tag_search_results("")  # Reset search results

        except Exception as e:
            self.show_message(f"Failed to add and assign tag: {str(e)}", "error")


    def create_remove_tag_command(self, tag_name):
        """Create a remove tag command with properly bound arguments."""
        def command():
            character_name = self.get_character_name()
            if character_name:  # Ensure a character name is provided
                self.remove_tag_and_refresh(tag_name, character_name)
            else:
                self.show_message("No character selected.", "error")
        return command


    def remove_tag_and_refresh(self, tag_name, character_name):
        print(f"Removing tag: {tag_name} from character: {character_name}")
        try:
            if not character_name:
                self.show_message("No character selected to remove the tag from.", "error")
                return

            # Unassign the tag using the SillyTavernTagManager
            self.tag_manager.unassign_tag(tag_name, character_name)
            print("Tag unassigned successfully.")  # Debug
            self.tag_manager.save_tags()
            print("Tags saved successfully.")  # Debug

            # Refresh tags in the UI
            self.load_tags_for_character(character_name)

            self.show_message(f"Tag '{tag_name}' removed successfully.", "success")
        except Exception as e:
            self.show_message(f"Failed to remove tag: {str(e)}", "error")


    def clear_tags(self):
        """Clear all tags displayed in the tag frames."""
        for frame in [
            self.assigned_tags_frame, self.potential_tags_frame
        ]:
            for widget in frame.winfo_children():
                widget.destroy()



######################################################################################################
######################################## Manage Lorebooks ############################################
######################################################################################################

    def open_lorebooks_modal_action(self):
        """Trigger the Lorebooks Modal."""
        open_lorebooks_modal(
            parent=self,  # Pass the main app as the parent
            lorebook_manager=self.lorebook_manager,  # Lorebook manager instance
            create_thumbnail_func=self.create_thumbnail,  # Method to create image thumbnails
            display_lorebooks_func=display_lorebooks,  # Function to display the lorebooks
            load_lorebook_details_func=load_lorebook_details,  # Function to load details of a selected lorebook
            handle_lorebook_save_func=handle_lorebook_save,  # Function to save lorebook changes
            add_image_modal_func=add_image_modal,  # Function to add an image modal
            open_link_character_modal_func=open_link_character_modal_for_lorebook,  # Link character modal function
            get_character_list_func=self.get_character_list,  # Function to retrieve a list of characters
            get_linked_characters_func=get_linked_characters,  # Function to retrieve linked characters
            handle_unlink_character_func=self.handle_unlink_character,  # Function to unlink characters
            align_modal_top_left_func=self._align_modal_top_left,  # Utility to align modal top-left
        )

    def refresh_lorebooks(self, scrollable_lorebooks, notes_textbox, misc_notes_textbox, filename_label, created_label, last_modified_label, lorebook_name_label, images_frame ):
        refresh_lorebooks(lorebook_manager=self.lorebook_manager, display_lorebooks_func=self.display_lorebooks, load_lorebook_details_func=self.load_lorebook_details, scrollable_lorebooks=scrollable_lorebooks, notes_textbox=notes_textbox, misc_notes_textbox=misc_notes_textbox, filename_label=filename_label, created_label=created_label, last_modified_label=last_modified_label, lorebook_name_label=lorebook_name_label, images_frame=images_frame)

    def display_lorebooks(self, frame, lorebooks, on_select):
        display_lorebooks(frame=frame, lorebooks=lorebooks, on_select=on_select, fg_color_default="#4b3e72",fg_color_selected="#d8bfd8")

    def load_lorebook_details(self, lorebook, notes_textbox, misc_notes_textbox, filename_label, created_label, last_modified_label, lorebook_name_label, images_frame,
    ):
        load_lorebook_details(lorebook=lorebook, notes_textbox=notes_textbox, misc_notes_textbox=misc_notes_textbox, filename_label=filename_label, created_label=created_label, last_modified_label=last_modified_label, lorebook_name_label=lorebook_name_label, images_frame=images_frame, linked_characters_frame=getattr(self, "linked_characters_frame", None), selected_lorebook_id=getattr(self, "selected_lorebook_id", None), set_selected_lorebook_id=lambda lorebook_id: setattr(self, "selected_lorebook_id", lorebook_id), load_images_func=self.lorebook_manager.load_images, display_images_func=self.display_images, get_linked_characters_func=lambda lorebook_id: get_linked_characters(self.db_manager.db_path, lorebook_id), display_linked_characters_func=display_linked_characters, handle_unlink_character_func=self.handle_unlink_character,)


    def handle_lorebook_save( 
            self, notes, misc_notes, filename, scrollable_lorebooks, notes_textbox, misc_notes_textbox, filename_label, created_label, last_modified_label, lorebook_name_label, images_frame,
    ): 
        handle_lorebook_save(notes=notes, misc_notes=misc_notes, filename=filename,save_lorebook_changes_func=self.lorebook_manager.save_lorebook_changes,
            refresh_lorebooks_callback=lambda: 
            self.refresh_lorebooks(scrollable_lorebooks,notes_textbox,misc_notes_textbox, filename_label, created_label, last_modified_label, lorebook_name_label, images_frame,),
            show_message_func=self.show_message,
        )

    ########## Lorebook Extra Images ####################
    def display_images(self, frame, images, lorebook):
        display_images(frame=frame, images=images, lorebook=lorebook, create_thumbnail_func=self.create_thumbnail, edit_image_func=self.edit_image, delete_image_func=self.delete_image,)

    def add_image_modal(self, lorebook_id, images_frame):
        add_image_modal(parent=self, lorebook_id=lorebook_id, images_frame=images_frame, browse_image_file_func=self.browse_image_file, save_image_func=self.lorebook_manager.save_image, refresh_images_func=self.refresh_images, show_message_func=self.show_message,)

    def edit_image(self, image_id, lorebook, images_frame):
        edit_image( parent=self, image_id=image_id, lorebook=lorebook, images_frame=images_frame, selected_lorebook_id=self.selected_lorebook_id, get_image_details_func=self.lorebook_manager.get_image_details, save_image_changes_func=self.save_image_changes, show_message_func=self.show_message,)

    def browse_image_file(self, entry_widget):
        browse_image_file(entry_widget)

    def save_image_changes(self, image_id, new_image_name, new_image_note, modal, images_frame, lorebook):
        save_image_changes( image_id=image_id, new_image_name=new_image_name, new_image_note=new_image_note, modal=modal, images_frame=images_frame, lorebook=lorebook, get_image_details_func=self.lorebook_manager.get_image_details, update_image_details_func=self.lorebook_manager.update_image_details, refresh_images_func=self.refresh_images, selected_lorebook_id=self.selected_lorebook_id, show_message_func=self.show_message,)

    def refresh_images(self, images_frame, lorebook_id, lorebook=None):
        refresh_images( images_frame=images_frame, lorebook_id=lorebook_id, lorebook=lorebook, get_lorebooks_list_func=self.lorebook_manager.get_lorebooks_list, load_images_func=self.lorebook_manager.load_images, display_images_func=self.display_images, show_message_func=self.show_message,)

    def delete_image(self, image_id, images_frame):
        delete_image( image_id=image_id, images_frame=images_frame, selected_lorebook_id=self.selected_lorebook_id, get_lorebooks_list_func=self.lorebook_manager.get_lorebooks_list, delete_image_func=self.lorebook_manager.delete_image, refresh_images_func=self.refresh_images, show_message_func=self.show_message, askyesno_func=askyesno,)


    ######## LOREBOOK LINK CHARACTERS #######################################################
    def update_linked_characters_display(self, lorebook_id):
        linked_characters = get_linked_characters(self.db_manager.db_path, lorebook_id)
        display_linked_characters(self.linked_characters_frame, linked_characters, self.handle_unlink_character, lorebook_id)


    def handle_link_character(self, char_id, lorebook_id):
        result = link_character_to_lorebook(self.db_manager.db_path, char_id, lorebook_id)
        self.show_message(result["message"], result["status"])
        if result["status"] == "success":
            linked_characters = get_linked_characters(self.db_manager.db_path, lorebook_id)
            
            if hasattr(self, "linked_characters_frame") and self.linked_characters_frame.winfo_exists():
                display_linked_characters(
                    self.linked_characters_frame,
                    linked_characters,
                    self.handle_unlink_character,
                    lorebook_id
                )
            else:
                self.show_message("Linked characters frame is not available.", "error")

    def handle_unlink_character(self, char_id, lorebook_id):
        result = unlink_character_from_lorebook(self.db_manager.db_path, char_id, lorebook_id)
        self.show_message(result["message"], result["status"])
        if result["status"] == "success":
            linked_characters = get_linked_characters(self.db_manager.db_path, lorebook_id)
            
            if hasattr(self, "linked_characters_frame") and self.linked_characters_frame.winfo_exists():
                display_linked_characters(
                    self.linked_characters_frame,
                    linked_characters,
                    self.handle_unlink_character,
                    lorebook_id
                )
            else:
                self.show_message("Linked characters frame is not available.", "error")

######################################################################################################
######################################## Utility Functions ###########################################
######################################################################################################

    def save_character_with_message(self):
        """Save the character to the database and SillyTavern, ensuring no conflicts with existing files."""
        file_path = Path(self.file_path_entry.get().strip())
        character_name = self.add_character_name_entry.get().strip()
        character_notes = self.add_character_notes_textbox.get("1.0", "end").strip()
        misc_notes = self.add_misc_notes_textbox.get("1.0", "end").strip()

        # Validate character name
        if not character_name:
            self.show_add_character_message("Please provide a character name.", "error")
            return

        # Validate that the file exists
        if not file_path.exists():
            self.show_add_character_message("Please select a file or import a card via the API.", "error")
            return

        # Ensure `sillytavern_path` is a Path object
        sillytavern_path = Path(self.settings["sillytavern_path"]).resolve() / "characters"
        sillytavern_path.mkdir(parents=True, exist_ok=True)  # Ensure the folder exists

        # Check if the file was imported (use flag) or browsed via file dialog
        is_imported = getattr(self, "is_imported_flag", False)
        final_file_path = sillytavern_path / file_path.name

        if not is_imported:
            # Handle conflict only for browsed files
            if final_file_path.exists():
                response = askyesno(
                    "File Conflict",
                    "The file already exists in your SillyTavern folder. Do you want to create a new copy?"
                )
                if response:
                    # Increment the filename until an unused one is found
                    base_name = final_file_path.stem
                    extension = final_file_path.suffix
                    counter = 1
                    while final_file_path.exists():
                        final_file_path = sillytavern_path / f"{base_name}_{counter}{extension}"
                        counter += 1
                    # Move the file to the new path
                    shutil.copy(str(file_path), str(final_file_path))
                else:
                    self.show_add_character_message("File import canceled due to name conflict.", "error")
                    return
            else:
                # Move the file if no conflict exists
                shutil.move(str(file_path), str(final_file_path))

        try:
            # Generate timestamps
            created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            last_modified_date = created_date

            # Add character data to the database
            connection = sqlite3.connect(self.db_manager.db_path)
            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO characters 
                (name, main_file, notes, misc_notes, created_date, last_modified_date) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (character_name, str(final_file_path), character_notes, misc_notes, created_date, last_modified_date),
            )
            connection.commit()

            # Get the newly created character ID
            new_character_id = cursor.lastrowid
            connection.close()

            # Add the character to the in-memory list
            new_character = {
                "id": new_character_id,
                "name": character_name,
                "image_path": str(final_file_path),  # Use the file directly in SillyTavern
                "created_date": created_date,
                "last_modified_date": last_modified_date,
            }
            self.all_characters.append(new_character)

            # Process tags if any exist in the metadata
            try:
                if hasattr(self, "latest_metadata"):  # Ensure metadata is loaded
                    tags = self.latest_metadata.get("tags", [])
                    tag_manager = SillyTavernTagManager(self.settings["sillytavern_path"])

                    for tag in tags:
                        # Assign tags to the character in the settings.json
                        tag_manager.assign_tag(tag.strip().lower(), character_name)

                    tag_manager.save_tags()  # Save the updated tags to settings.json
            except Exception as e:
                print(f"Error processing tags: {e}")

            # Refresh filtered characters and display
            self.filter_character_list()
            self.sort_character_list(self.sort_var.get())

            # Highlight the new character
            self.select_character_by_id(new_character_id)

            # Show success message and close the modal
            self.show_add_character_message("Character added successfully!", "success")
            self.add_character_window.after(500, self.add_character_window.destroy())

        except Exception as e:
            self.show_add_character_message(f"Error saving character: {str(e)}", "error")


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


    def show_message(self, message, message_type="error"):
        """
        Show a pop-up message in the top-right corner of the currently focused or active window/modal without a title bar.
        Args:
            message: The message to display.
            message_type: Type of message ("error" or "success").
        """
        # Determine the root or top-level window
        focused_widget = self.focus_get()  # Get the currently focused widget
        caller = focused_widget.winfo_toplevel() if focused_widget else self

        # Create a pop-up window
        popup = ctk.CTkToplevel(caller)
        popup.overrideredirect(True)  # Remove title bar
        popup.geometry("300x80")  # Adjust size for wrapped text
        popup.attributes("-topmost", True)
        popup.transient(caller)  # Tie the pop-up to the caller

        # Determine the caller's position
        caller_x = caller.winfo_rootx()
        caller_y = caller.winfo_rooty()
        caller_width = caller.winfo_width()

        # Calculate the top-right position relative to the caller
        x = caller_x + caller_width - 460  # Adjust for pop-up width
        y = caller_y + 0  # Slight padding from the top
        popup.geometry(f"+{x}+{y}")

        # Configure the pop-up appearance
        if message_type == "success":
            popup_color = "#C8E6C9"  # Green for success
            text_color = "black"
        else:
            popup_color = "#FFCDD2"  # Red for error
            text_color = "black"

        popup.configure(fg_color=popup_color)

        # Add a label with wrapped text
        label = ctk.CTkLabel(
            popup,
            text=message,
            text_color=text_color,
            font=("Arial", 12),
            wraplength=280,  # Enable wrapping within the notification width
            anchor="center",  # Center the text
            justify="center",  # Center justify the text
        )
        label.pack(padx=10, pady=10, fill="both", expand=True)

        # Automatically close the pop-up after 3 seconds
        popup.after(3000, popup.destroy)

    def get_character_name(self):
        """Retrieve the character's name using the selected character ID."""
        connection = sqlite3.connect(self.db_manager.db_path)
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM characters WHERE id = ?", (self.selected_character_id,))
        result = cursor.fetchone()
        connection.close()
        return result[0] if result else "Unknown"
    
    def format_date(self, date_string):
        """Format a date string for display."""
        try:
            date_obj = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            return date_obj.strftime("%m/%d/%Y %I:%M %p")
        except Exception:
            return "Unknown Date"
        
    def truncate_to_100_words(self, text):
        """
        Truncate the text to 100 words, ensuring it ends at the nearest sentence.
        """
        words = text.split()
        if len(words) <= 100:
            return text

        truncated = " ".join(words[:100])
        if "." in truncated:
            truncated = truncated[:truncated.rfind(".") + 1]  # Trim to the last full sentence

        return truncated


    def export_data(self):
        print("Export Data clicked")

        
    def debounce_search(self, *args):
        """Debounce the search input to prevent rapid calls."""
        # Cancel the existing timer if there is one
        if self.search_debounce_timer is not None:
            self.after_cancel(self.search_debounce_timer)

        # Set a new timer to execute the actual search function
        self.search_debounce_timer = self.after(300, self.filter_character_list)

    def create_thumbnail(self, image_path, callback=None, widget_ref=None):
        """Create a thumbnail for the character list using CTkImage with thread-safe UI updates."""
        def load_thumbnail():
            try:
                img = Image.open(image_path)

                # Calculate the target aspect ratio
                target_aspect_ratio = 50 / 75
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
                thumbnail = ctk.CTkImage(img, size=(50, 75))
            except Exception:
                # Fallback to default image if loading fails
                default_img = Image.open("assets/default_thumbnail.png")
                thumbnail = ctk.CTkImage(default_img, size=(50, 75))

            # If a callback is provided, pass the thumbnail to it
            if callback:
                self.thumbnail_queue.put((callback, thumbnail, widget_ref))
            else:
                # Return the thumbnail directly for non-async calls
                return thumbnail

        # Start the thumbnail loading in a separate thread if a callback is provided
        if callback:
            threading.Thread(target=load_thumbnail, daemon=True).start()
        else:
            return load_thumbnail()



    def process_thumbnail_queue(self):
        """Process thumbnails from the queue on the main thread."""
        try:
            while not self.thumbnail_queue.empty():
                callback, thumbnail, widget_ref = self.thumbnail_queue.get_nowait()

                # Check if the widget reference is still valid
                if widget_ref:
                    widget = widget_ref()
                    if widget and widget.winfo_exists():
                        callback(widget, thumbnail)
                else:
                    # If no widget_ref, directly call the callback
                    callback(thumbnail)
        except queue.Empty:
            pass
        # Schedule the next check
        self.after(100, self.process_thumbnail_queue)


    def update_thumbnail_label(self, widget, thumbnail):
        """Safely update the thumbnail label with a new image."""
        if widget and widget.winfo_exists():
            widget.configure(image=thumbnail)

        
    def create_thumbnail_small(self, image_path):
        """Create a thumbnail for the character list using CTkImage."""
        try:
            # Open the image
            img = Image.open(image_path)

            # Calculate the target aspect ratio
            target_aspect_ratio = 25 / 37.5

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
            img = img.resize((25, 37.5), Image.Resampling.LANCZOS)

            # Return the resized image wrapped in a CTkImage
            return ctk.CTkImage(img, size=(25, 37.5))
        except Exception:
            # Use default thumbnail if image cannot be loaded
            default_img = Image.open("assets/default_thumbnail.png")
            return ctk.CTkImage(default_img, size=(25, 37.5))

    def bind_mouse_wheel(self, frame, parent_frame=None):
        """Bind the mouse wheel event to a CTkScrollableFrame and prioritize it when hovered."""
        def _on_mouse_wheel(event):
            # Safely check if the frame's canvas exists before scrolling
            if hasattr(frame, "_parent_canvas") and frame._parent_canvas:
                frame._parent_canvas.yview_scroll(-1 * int(event.delta / 10), "units")
            else:
                # Remove any lingering bindings if the canvas is gone
                frame.unbind_all("<MouseWheel>")
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

####################################################
##################### MODAL CLASS ##################
####################################################

class MultiSelectModal(ctk.CTkToplevel):
    def __init__(self, parent, title, options, selected_options, callback):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x400")
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

            # Reset the scrollbar to the top
        self.scrollable_frame.update_idletasks()
        self.scrollable_frame._parent_canvas.yview_moveto(0)

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
