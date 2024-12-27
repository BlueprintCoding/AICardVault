from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog


class SettingsModal:
    def __init__(self, parent, db_manager, update_settings_callback):
        self.parent = parent
        self.db_manager = db_manager
        self.update_settings_callback = update_settings_callback

    def open(self):
        # Create the modal window
        self.modal = ctk.CTkToplevel(self.parent)
        self.modal.title("Settings")
        self.modal.geometry("350x225")

        # Ensure the modal stays on top of the main window
        self.modal.transient(self.parent)
        self.modal.grab_set()

        # Align the modal to the top-left corner of the parent window
        self._align_modal_top_left(self.modal, self.parent)

        # Load current settings
        current_appearance = self.db_manager.get_setting("appearance_mode", "dark")
        current_path = self.db_manager.get_setting("sillytavern_path", "")
        current_sort_order = self.db_manager.get_setting("default_sort_order", "A - Z")
        items_per_page = self.db_manager.get_setting("items_per_page", "5")
        tags_per_page = self.db_manager.get_setting("tags_per_page", "10")


        # Appearance Mode Option
        appearance_label = ctk.CTkLabel(self.modal, text="Appearance Mode:")
        appearance_label.pack(pady=(5,0), padx=10, anchor="w")

        self.appearance_option = ctk.CTkOptionMenu(
            self.modal,
            values=["Dark", "Light"],
        )
        self.appearance_option.set(current_appearance.capitalize())
        self.appearance_option.pack(pady=0, padx=10, fill="x")

        # SillyTavern Path Selection
        path_label = ctk.CTkLabel(self.modal, text="Path to SillyTavern User Folder:")
        path_label.pack(pady=(5, 0), padx=10, anchor="w")

        # Create a frame to hold the path entry and browse button
        path_frame = ctk.CTkFrame(self.modal, fg_color="transparent")
        path_frame.pack(pady=(0, 5), padx=10, fill="x")

        # Path Entry
        self.path_entry = ctk.CTkEntry(path_frame)
        self.path_entry.insert(0, current_path)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Browse Button
        browse_button = ctk.CTkButton(
            path_frame, text="Browse", command=self.browse_folder
        )
        browse_button.pack(side="right")


        # Default Sort Order
        sort_order_label = ctk.CTkLabel(self.modal, text="Default Card Sort Order:")
        sort_order_label.pack(pady=(5,0), padx=10, anchor="w")

        self.sort_order_option = ctk.CTkOptionMenu(
            self.modal,
            values=["A - Z", "Z - A", "Newest", "Oldest", "Most Recently Edited"],
        )
        self.sort_order_option.set(current_sort_order)
        self.sort_order_option.pack(pady=0, padx=10, fill="x")

        # Create a frame for items and tags per page
        per_page_frame = ctk.CTkFrame(self.modal, fg_color="transparent")
        per_page_frame.pack(pady=(10, 0), padx=10, fill="x")

        # Items Per Page
        items_per_page_label = ctk.CTkLabel(per_page_frame, text="Cards Per Page:")
        items_per_page_label.pack(side="left", padx=(0, 5))

        self.items_per_page_entry = ctk.CTkEntry(per_page_frame, width=100)
        self.items_per_page_entry.insert(0, items_per_page)
        self.items_per_page_entry.pack(side="left", padx=(0, 15))

        # Tags Per Page
        tags_per_page_label = ctk.CTkLabel(per_page_frame, text="Tags Per Page:")
        tags_per_page_label.pack(side="left", padx=(0, 5))

        self.tags_per_page_entry = ctk.CTkEntry(per_page_frame, width=100)
        self.tags_per_page_entry.insert(0, tags_per_page)
        self.tags_per_page_entry.pack(side="left")

        # Warning for Per Page Settings
        per_page_warning = ctk.CTkLabel(
            self.modal,
            text="Setting these numbers too high can cause slow loading or a laggy UI.",
            font=ctk.CTkFont(size=10, weight="normal"),
            text_color="orange"
        )
        per_page_warning.pack(pady=(5, 0), padx=10, anchor="w")


        # Save Button
        save_button = ctk.CTkButton(self.modal, text="Save", command=self.save_settings)
        save_button.pack(pady=10, padx=10, anchor="e")

    def browse_folder(self):
        """Open a folder dialog to select the SillyTavern folder."""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, Path(folder_path))

    def save_settings(self):
        """Save the updated settings to the database."""
        appearance_mode = self.appearance_option.get().lower()
        sillytavern_path = Path(self.path_entry.get())
        default_sort_order = self.sort_order_option.get()
        items_per_page = self.items_per_page_entry.get().strip()
        tags_per_page = self.tags_per_page_entry.get().strip()

        # Update the database
        self.db_manager.set_setting("appearance_mode", appearance_mode)
        self.db_manager.set_setting("sillytavern_path", str(sillytavern_path))
        self.db_manager.set_setting("default_sort_order", default_sort_order)
        self.db_manager.set_setting("items_per_page", items_per_page)
        self.db_manager.set_setting("tags_per_page", tags_per_page)

        # Callback to update settings in the main app
        self.update_settings_callback({
            "appearance_mode": appearance_mode,
            "sillytavern_path": str(sillytavern_path),
            "default_sort_order": default_sort_order,
            "items_per_page": items_per_page,
            "tags_per_page": tags_per_page,
        })

        # Close the modal
        self.modal.destroy()

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
