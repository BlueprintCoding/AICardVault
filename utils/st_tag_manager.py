import json
from pathlib import Path
import customtkinter as ctk
from customtkinter import CTkInputDialog
from tkinter import messagebox
import uuid
import time

class TagsManager:
    def __init__(self, master, sillytavern_path, on_tags_updated=None):
        self.master = master
        self.sillytavern_path = sillytavern_path
        self.tags_data = []
        self.tag_map = {}
        self.sort_criteria = "# of Characters (Desc)"
        self.bulk_delete_mode = False
        self.selected_tags = set()
        self.selected_tag_frame = None
        self.on_tags_updated = on_tags_updated
        self.current_page = 0  # Track the current page
        self.tags_per_page = 10  # Number of tags per page

    def open(self):
        """Open the tags management modal."""
        settings_path = Path(self.sillytavern_path) / "settings.json"
        if not settings_path.exists():
            messagebox.showerror("Error", "Settings.json not found. The SillyTavern path is incorrect or the file is missing.")
            return

        try:
            with settings_path.open("r", encoding="utf-8") as f:
                settings = json.load(f)
            self.tags_data = settings.get("tags", [])
            self.tag_map = settings.get("tag_map", {})
            self.filtered_tags = self.tags_data.copy()
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            messagebox.showerror("Error", f"Failed to load settings.json: {e}")
            return

        # Create modal window
        self.modal = ctk.CTkToplevel(self.master)
        self.modal.title("Manage SillyTavern Tags")
        self.modal.geometry("800x400")
        self.modal.transient(self.master)
        self.modal.grab_set()

        # Configure grid weights
        self.modal.grid_columnconfigure(0, weight=1)  # controls frame
        self.modal.grid_columnconfigure(1, weight=1)  # tags frame
        self.modal.grid_columnconfigure(2, weight=2)  # characters frame
        self.modal.grid_rowconfigure(1, weight=1)     # middle row for content

        # Controls Frame
        controls_frame = ctk.CTkFrame(self.modal)
        controls_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure((0,1,2,3), weight=1)

        # Search Bar
        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(
            controls_frame,
            textvariable=self.search_var,
            placeholder_text="Search tags...",
            width=200
        )
        search_entry.grid(row=0, column=0, padx=5)
        self.search_var.trace_add("write", lambda *args: self.filter_tags())

        # Sort Dropdown
        self.sort_var = ctk.StringVar(value="# of Characters (Desc)")
        sort_options = ["A-Z", "Z-A", "Create Date (Asc)", "Create Date (Desc)", "# of Characters (Asc)", "# of Characters (Desc)"]
        sort_dropdown = ctk.CTkOptionMenu(
            controls_frame,
            variable=self.sort_var,
            values=sort_options,
            command=self.sort_tags
        )
        sort_dropdown.grid(row=0, column=1, padx=5)

        # Add Tag Button
        add_tag_button = ctk.CTkButton(
            controls_frame,
            text="Add Tag",
            command=self.add_new_tag
        )
        add_tag_button.grid(row=0, column=2, padx=5)

        # Bulk Delete Button
        self.bulk_delete_button = ctk.CTkButton(
            controls_frame,
            text="Bulk Delete",
            command=self.toggle_bulk_delete_mode
        )
        self.bulk_delete_button.grid(row=0, column=3, padx=5)

        # Tags List
        self.tags_frame = ctk.CTkScrollableFrame(self.modal, width=400)
        self.tags_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        # Characters Frame
        self.characters_frame = ctk.CTkScrollableFrame(self.modal)
        self.characters_frame.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=10, pady=10)

        # Pagination Frame - Now in row 2, below tags_frame
        self.pagination_frame = ctk.CTkFrame(self.modal)
        self.pagination_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10))
        self.pagination_frame.grid_columnconfigure((0,1,2), weight=1)


        # Pagination Controls
        self.prev_button = ctk.CTkButton(
            self.pagination_frame,
            text="Previous",
            command=self.go_to_previous_page
        )
        self.prev_button.grid(row=0, column=0, padx=1, pady=5)

        self.page_label = ctk.CTkLabel(
            self.pagination_frame,
            text="",
            anchor="center"
        )
        self.page_label.grid(row=0, column=1, padx=2, pady=5)

        self.next_button = ctk.CTkButton(
            self.pagination_frame,
            text="Next",
            command=self.go_to_next_page
        )
        self.next_button.grid(row=0, column=2, padx=1, pady=5)

        # Default sort and populate tags
        self.sort_tags(self.sort_var.get())

    def add_pagination_controls(self):
        """Update pagination controls."""
        self.page_label.configure(text=f"Page {self.current_page + 1} of {self.total_pages()}")
        self.prev_button.configure(state="normal" if self.current_page > 0 else "disabled")
        self.next_button.configure(state="normal" if self.current_page < self.total_pages() - 1 else "disabled")

 
    def populate_tags(self):
            """Display the list of tags with pagination."""
            for widget in self.tags_frame.winfo_children():
                widget.destroy()

            # Calculate start and end indices for the current page
            start_index = self.current_page * self.tags_per_page
            end_index = start_index + self.tags_per_page
            visible_tags = self.filtered_tags[start_index:end_index]

            # Call add_pagination_controls AFTER clearing the tags but BEFORE populating new tags
            self.add_pagination_controls()
            
            # Display the tags for the current page
            for tag in visible_tags:
                tag_id = tag["id"]
                tag_name = tag["name"]
                character_count = sum(1 for char_tags in self.tag_map.values() if tag_id in char_tags)

                # Frame for each tag
                tag_frame = ctk.CTkFrame(self.tags_frame)
                tag_frame.pack(fill="x", padx=5, pady=5)

                if self.bulk_delete_mode:
                    # Checkbox for bulk delete
                    checkbox_var = ctk.BooleanVar(value=tag_id in self.selected_tags)
                    checkbox = ctk.CTkCheckBox(
                        tag_frame,
                        text="",
                        variable=checkbox_var,
                        command=lambda tag_id=tag_id, var=checkbox_var: self.toggle_tag_selection(tag_id, var)
                    )
                    checkbox.pack(side="left", padx=5)

                # Tag Name
                tag_label = ctk.CTkLabel(tag_frame, text=f"{tag_name} ({character_count})")
                tag_label.pack(side="left", padx=5)

                if not self.bulk_delete_mode:
                    # Rename Button
                    rename_button = ctk.CTkButton(
                        tag_frame,
                        text="Rename",
                        width=60,
                        command=lambda tag=tag: self.rename_tag(tag)
                    )
                    rename_button.pack(side="right", padx=5)

                    # Delete Button
                    delete_button = ctk.CTkButton(
                        tag_frame,
                        text="Delete",
                        width=60,
                        fg_color="red",
                        hover_color="darkred",
                        command=lambda tag=tag: self.delete_tag(tag)
                    )
                    delete_button.pack(side="right", padx=5)

                # Clickable label to load characters
                tag_label.bind("<Button-1>", lambda e, tag_id=tag_id, frame=tag_frame: self.show_characters(tag_id, frame))

    def total_pages(self):
        """Calculate the total number of pages."""
        return (len(self.filtered_tags) + self.tags_per_page - 1) // self.tags_per_page

    def go_to_previous_page(self):
        """Navigate to the previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.populate_tags()

    def go_to_next_page(self):
        """Navigate to the next page."""
        if self.current_page < self.total_pages() - 1:
            self.current_page += 1
            self.populate_tags()

    def filter_tags(self):
        """Filter tags based on the search input and reset to the first page."""
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered_tags = self.tags_data.copy()
        else:
            self.filtered_tags = [
                tag for tag in self.tags_data if query in tag["name"].lower()
            ]
        self.current_page = 0  # Reset to the first page
        self.populate_tags()

    def add_new_tag(self):
        """Add a new tag to the tags JSON."""
        # Prompt user for the tag name
        dialog = CTkInputDialog(
            text="Enter the name for the new tag:",
            title="Add New Tag"
        )
        tag_name = dialog.get_input()  # Wait for user input

        if not tag_name:
            messagebox.showwarning("Warning", "Tag name cannot be empty.")
            return

        # Create the new tag object
        new_tag = {
            "id": str(uuid.uuid4()),  # Generate a unique ID
            "name": tag_name.strip(),
            "folder_type": "NONE",
            "filter_state": "UNDEFINED",
            "sort_order": max((tag.get("sort_order") or 0 for tag in self.tags_data), default=0) + 1,
            "color": "",
            "color2": "",
            "create_date": int(time.time() * 1000),  # Current time in milliseconds
        }

        # Add the new tag to the tags data
        self.tags_data.append(new_tag)

        # Save changes to the JSON
        self.save_changes()

        # Refresh the tags list
        self.filter_tags()

    def toggle_bulk_delete_mode(self):
        """Toggle between bulk delete mode and normal mode."""
        if self.bulk_delete_mode:  # If already in bulk delete mode, delete the selected tags
            self.delete_selected_tags()
        else:  # Enter bulk delete mode
            self.bulk_delete_mode = True
            self.bulk_delete_button.configure(text="Delete Selected")
            self.selected_tags.clear()  # Clear any previous selections
            self.populate_tags()  # Refresh the tags display


    def toggle_tag_selection(self, tag_id, var):
        """Toggle tag selection for bulk delete."""
        if var.get():
            self.selected_tags.add(tag_id)
        else:
            self.selected_tags.discard(tag_id)

    def delete_selected_tags(self):
        """Delete all selected tags in bulk."""
        if not self.selected_tags:
            messagebox.showinfo("No Tags Selected", "Please select tags to delete.")
            return

        confirm = messagebox.askyesno(
            "Confirm Bulk Delete",
            f"Are you sure you want to delete {len(self.selected_tags)} selected tags?"
        )
        if confirm:
            # Remove selected tags from tags_data
            self.tags_data = [t for t in self.tags_data if t["id"] not in self.selected_tags]

            # Remove the selected tag IDs from tag_map
            for char, tags in self.tag_map.items():
                self.tag_map[char] = [t for t in tags if t not in self.selected_tags]

            # Save changes
            self.save_changes()

            # Exit bulk delete mode
            self.bulk_delete_mode = False
            self.bulk_delete_button.configure(text="Bulk Delete")
            self.selected_tags.clear()

            # Refresh filtered tags and UI
                    # Clear search and refresh the tags list
            self.search_var.set("")  # Clear the search field
            self.filtered_tags = self.tags_data.copy()  # Reset filtered tags
            self.filter_tags()

    def sort_tags(self, sort_option):
        """Sort tags based on the selected criteria."""
        if sort_option == "A-Z":
            self.filtered_tags.sort(key=lambda tag: tag["name"].lower())
        elif sort_option == "Z-A":
            self.filtered_tags.sort(key=lambda tag: tag["name"].lower(), reverse=True)
        elif sort_option == "Create Date (Asc)":
            self.filtered_tags.sort(key=lambda tag: tag.get("create_date", 0))
        elif sort_option == "Create Date (Desc)":
            self.filtered_tags.sort(key=lambda tag: tag.get("create_date", 0), reverse=True)
        elif sort_option == "# of Characters (Asc)":
            self.filtered_tags.sort(
                key=lambda tag: sum(1 for char_tags in self.tag_map.values() if tag["id"] in char_tags)
            )
        elif sort_option == "# of Characters (Desc)":
            self.filtered_tags.sort(
                key=lambda tag: sum(1 for char_tags in self.tag_map.values() if tag["id"] in char_tags), reverse=True
            )

        # Refresh the tags list
        self.populate_tags()


    def rename_tag(self, tag):
        """Rename a tag using CTkInputDialog."""
        dialog = CTkInputDialog(
            text=f"Enter new name for tag '{tag['name']}':",
            title="Rename Tag"
        )
        new_name = dialog.get_input()  # Waits for input

        if new_name:
            tag["name"] = new_name.strip()  # Ensure no trailing whitespace
            self.save_changes()
            self.populate_tags()

    def delete_tag(self, tag):
        """Delete a tag."""
        confirm = messagebox.askyesno("Delete Tag", f"Are you sure you want to delete the tag '{tag['name']}'?")
        if confirm:
            # Remove the tag from tags_data
            self.tags_data = [t for t in self.tags_data if t["id"] != tag["id"]]
            
            # Remove the tag ID from tag_map
            for char, tags in self.tag_map.items():
                if tag["id"] in tags:
                    self.tag_map[char] = [t for t in tags if t != tag["id"]]
            
            # Save changes and refresh the UI
            self.save_changes()
            self.search_var.set("")  # Clear the search field
            self.filtered_tags = self.tags_data.copy()  # Reset filtered tags
            self.filter_tags()


    def show_characters(self, tag_id, frame):
        """Show the characters associated with a tag and highlight the selected tag."""
        # Clear the characters frame
        for widget in self.characters_frame.winfo_children():
            widget.destroy()

        # Add a label above the characters list
        label = ctk.CTkLabel(self.characters_frame, text="Characters with Tag", anchor="w")
        label.pack(fill="x", padx=10, pady=5)

        # List of characters associated with the tag
        associated_characters = [
            char for char, tags in self.tag_map.items() if tag_id in tags
        ]

        # Separate valid characters and dead references
        valid_characters = [char for char in associated_characters if char.endswith(".png")]
        dead_references = [char for char in associated_characters if not char.endswith(".png")]

        # Variable to track checkboxes
        self.character_checkboxes = {}
        self.current_tag_id = tag_id

        if not associated_characters:
            no_characters_label = ctk.CTkLabel(self.characters_frame, text="No characters associated with this tag.")
            no_characters_label.pack(pady=10)
            return

        # Add valid characters
        for character in valid_characters:
            var = ctk.BooleanVar(value=True)
            checkbox = ctk.CTkCheckBox(
                self.characters_frame,
                text=character.replace(".png", ""),  # Display without .png for clarity
                variable=var
            )
            checkbox.pack(anchor="w", padx=10, pady=2)
            self.character_checkboxes[character] = var

        # Add dead references
        if dead_references:
            dead_label = ctk.CTkLabel(self.characters_frame, text="Deleted Cards Linked", anchor="w")
            dead_label.pack(fill="x", padx=10, pady=5)

            for reference in dead_references:
                var = ctk.BooleanVar(value=True)
                checkbox = ctk.CTkCheckBox(
                    self.characters_frame,
                    text=f"Deleted: {reference}",
                    variable=var,
                    fg_color="darkred"
                )
                checkbox.pack(anchor="w", padx=10, pady=2)
                self.character_checkboxes[reference] = var

        # Save button to remove unselected characters
        save_button = ctk.CTkButton(
            self.characters_frame,
            text="Save",
            command=self.save_character_changes
        )
        save_button.pack(pady=10)

        # Highlight the clicked tag row
        if self.selected_tag_frame and self.selected_tag_frame.winfo_exists():
            self.selected_tag_frame.configure(fg_color="#212121")  # Reset previous selection color
        self.selected_tag_frame = frame
        self.selected_tag_frame.configure(fg_color="#3d3061")  # Highlight the new selection


    def save_character_changes(self):
        """Save changes to character associations for the selected tag."""
        if not self.current_tag_id:
            messagebox.showerror("Error", "No tag selected.")
            return

        # Update the tag map based on unchecked characters
        for character, var in self.character_checkboxes.items():
            if not var.get():  # If the checkbox is unchecked
                if character in self.tag_map:
                    # Remove the tag ID from the character's tag list
                    self.tag_map[character] = [
                        tag_id for tag_id in self.tag_map[character] if tag_id != self.current_tag_id
                    ]

                    # Remove character completely if it has no tags left
                    if not self.tag_map[character]:
                        del self.tag_map[character]

        # Save changes to the tag map
        self.save_changes()

        # Refresh the characters frame
        self.show_characters(self.current_tag_id, self.selected_tag_frame)

        # Refresh the tags list to update character counts
        self.populate_tags()

    def save_changes(self):
        """Save changes to settings.json."""
        settings_path = Path(self.sillytavern_path) / "settings.json"
        try:
            with settings_path.open("r", encoding="utf-8") as f:
                settings = json.load(f)

            settings["tags"] = self.tags_data
            settings["tag_map"] = self.tag_map

            with settings_path.open("w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)

            if self.on_tags_updated:
                self.on_tags_updated()

            messagebox.showinfo("Success", "Changes saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings.json: {e}")