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
        self.modal.geometry("400x350")

        # Ensure the modal stays on top of the main window
        self.modal.transient(self.parent)
        self.modal.grab_set()

        # Align the modal to the top-left corner of the parent window
        self._align_modal_top_left(self.modal, self.parent)

        # Load current settings
        current_appearance = self.db_manager.get_setting("appearance_mode", "dark")
        current_path = self.db_manager.get_setting("sillytavern_path", "")
        current_sort_order = self.db_manager.get_setting("default_sort_order", "A - Z")

        # Appearance Mode Option
        appearance_label = ctk.CTkLabel(self.modal, text="Appearance Mode:")
        appearance_label.pack(pady=10, padx=10, anchor="w")

        self.appearance_option = ctk.CTkOptionMenu(
            self.modal,
            values=["Dark", "Light"],
        )
        self.appearance_option.set(current_appearance.capitalize())
        self.appearance_option.pack(pady=5, padx=10, fill="x")

        # SillyTavern Path Selection
        path_label = ctk.CTkLabel(self.modal, text="Path to SillyTavern User Folder:")
        path_label.pack(pady=10, padx=10, anchor="w")

        self.path_entry = ctk.CTkEntry(self.modal, width=300)
        self.path_entry.insert(0, current_path)
        self.path_entry.pack(pady=5, padx=10, fill="x")

        browse_button = ctk.CTkButton(
            self.modal, text="Browse", command=self.browse_folder
        )
        browse_button.pack(pady=5, padx=10, anchor="e")

        # Default Sort Order
        sort_order_label = ctk.CTkLabel(self.modal, text="Default Sort Order:")
        sort_order_label.pack(pady=10, padx=10, anchor="w")

        self.sort_order_option = ctk.CTkOptionMenu(
            self.modal,
            values=["A - Z", "Z - A", "Newest", "Oldest", "Most Recently Edited"],
        )
        self.sort_order_option.set(current_sort_order)
        self.sort_order_option.pack(pady=5, padx=10, fill="x")

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

        # Update the database
        self.db_manager.set_setting("appearance_mode", appearance_mode)
        self.db_manager.set_setting("sillytavern_path", str(sillytavern_path))
        self.db_manager.set_setting("default_sort_order", default_sort_order)

        # Callback to update settings in the main app
        self.update_settings_callback({
            "appearance_mode": appearance_mode,
            "sillytavern_path": str(sillytavern_path),
            "default_sort_order": default_sort_order,
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
