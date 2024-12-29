from pathlib import Path
import sqlite3
import customtkinter as ctk
from tkinter import Toplevel
from tkinter.filedialog import askopenfilename
from PIL import Image
from datetime import datetime
import shutil

DB_DIR = Path.cwd() / "db"
db_path = DB_DIR / "database.db"

####### Lorebook Main Modal #################
def open_lorebooks_modal(
    parent,
    lorebook_manager,
    display_lorebooks_func,
    load_lorebook_details_func,
    add_image_modal_func,
    open_link_character_modal_func,
    handle_lorebook_save_func,
    create_thumbnail_func,
    get_character_list_func,
    get_linked_characters_func,
    handle_unlink_character_func,
    align_modal_top_left_func,
):
    """Open a modal to manage lorebooks."""
    # Create modal window
    lorebooks_modal = ctk.CTkToplevel(parent)
    lorebooks_modal.title("Manage Lorebooks")
    lorebooks_modal.geometry("1200x700")
    lorebooks_modal.transient(parent)
    lorebooks_modal.grab_set()

    # Configure layout
    lorebooks_modal.grid_columnconfigure(0, weight=1)
    lorebooks_modal.grid_columnconfigure(1, weight=2)
    lorebooks_modal.grid_rowconfigure(0, weight=1)

    # Left Column - Lorebooks List
    list_frame = ctk.CTkFrame(lorebooks_modal, corner_radius=0)
    list_frame.grid(row=0, column=0, sticky="nswe", padx=10, pady=10)

    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(
        list_frame, textvariable=search_var, placeholder_text="Search lorebooks...", width=300
    )
    search_entry.pack(pady=(10, 5), padx=10)

    sort_var = ctk.StringVar(value="A - Z")
    sort_dropdown = ctk.CTkOptionMenu(
        list_frame,
        values=["A - Z", "Z - A", "Newest", "Oldest"],
        variable=sort_var,
        command=lambda order: sort_lorebooks(order),
    )
    sort_dropdown.pack(pady=(5, 10), padx=10)

    scrollable_lorebooks = ctk.CTkScrollableFrame(list_frame)
    scrollable_lorebooks.pack(fill="both", expand=True, padx=10, pady=10)

    # Right Column - Details
    details_frame = ctk.CTkFrame(lorebooks_modal, corner_radius=0)
    details_frame.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)

    lorebook_name_label = ctk.CTkLabel(
        details_frame, text="Select a Lorebook", font=("Arial", 16, "bold")
    )
    lorebook_name_label.pack(pady=(10, 5), padx=10)

    tabview = ctk.CTkTabview(details_frame)
    tabview.pack(fill="both", expand=True, padx=10, pady=10)

    # Notes Tab
    notes_tab = tabview.add("Notes")
    notes_label = ctk.CTkLabel(notes_tab, text="Lorebook Notes:")
    notes_label.pack(pady=5, padx=10, anchor="w")

    notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
    notes_textbox.pack(fill="both", expand=True, padx=10, pady=5)

    misc_notes_label = ctk.CTkLabel(notes_tab, text="Miscellaneous Notes:")
    misc_notes_label.pack(pady=5, padx=10, anchor="w")

    misc_notes_textbox = ctk.CTkTextbox(notes_tab, height=150)
    misc_notes_textbox.pack(fill="both", expand=True, padx=10, pady=5)

    # Images Tab
    images_tab = tabview.add("Images")
    images_frame = ctk.CTkScrollableFrame(images_tab)
    images_frame.pack(fill="both", expand=True, padx=10, pady=10)

    add_image_button = ctk.CTkButton(
        images_tab,
        text="Add Image",
        command=lambda: add_image_modal(
            parent=parent,
            lorebook_id=getattr(parent, "selected_lorebook_id", None),
            images_frame=images_frame,
            browse_image_file_func=browse_image_file,
            refresh_images_func=lambda images_frame, lorebook_id: refresh_images(
                images_frame=images_frame,
                lorebook_id=lorebook_id,
                lorebook=None,
                get_lorebooks_list_func=lorebook_manager.get_lorebooks_list,
                load_images_func=lorebook_manager.load_images,
                display_images_func=parent.display_images,
                show_message_func=parent.show_message,
            ),
            show_message_func=parent.show_message,
        ),
    )
    add_image_button.pack(pady=(10, 0))

    # Linked Characters Tab
    # Linked Characters Tab
    linked_characters_tab = tabview.add("Characters")
    link_characters_button = ctk.CTkButton(
        linked_characters_tab,
        text="Link Characters",
        command=lambda: open_link_character_modal_func(
            parent=parent,
            lorebook_id=getattr(parent, "selected_lorebook_id", None),
            create_thumbnail=create_thumbnail_func,
            get_character_list=get_character_list_func,
            linked_character_ids_func=lorebook_manager.get_linked_character_ids,
            handle_link_character_func=parent.handle_link_character,
            align_modal_top_left=align_modal_top_left_func,
        ),
    )
    link_characters_button.pack(pady=(10, 5), padx=10)

    # Assign linked_characters_frame to parent for later use
    if hasattr(parent, "linked_characters_frame"):
        parent.linked_characters_frame.destroy()  # Ensure no lingering frame
    parent.linked_characters_frame = ctk.CTkScrollableFrame(linked_characters_tab)
    parent.linked_characters_frame.pack(fill="both", expand=True, padx=10, pady=10)

        
        # Metadata Tab
    metadata_tab = tabview.add("Metadata")

    metadata_label = ctk.CTkLabel(metadata_tab, text="Filename:")
    metadata_label.pack(pady=5, padx=10, anchor="w")

    filename_label = ctk.CTkLabel(metadata_tab, text="", wraplength=500)
    filename_label.pack(pady=5, padx=10, anchor="w")

    created_label = ctk.CTkLabel(metadata_tab, text="Created Date:")
    created_label.pack(pady=5, padx=10, anchor="w")

    last_modified_label = ctk.CTkLabel(metadata_tab, text="Last Modified Date:")
    last_modified_label.pack(pady=5, padx=10, anchor="w")

    # Save Button
    save_button = ctk.CTkButton(
        details_frame,
        text="Save Changes",
        command=lambda: handle_lorebook_save_func(
            notes_textbox.get("1.0", "end").strip(),
            misc_notes_textbox.get("1.0", "end").strip(),
            filename_label.cget("text"),
            scrollable_lorebooks,
            notes_textbox,
            misc_notes_textbox,
            filename_label,
            created_label,
            last_modified_label,
            lorebook_name_label,
            images_frame,
        ),
    )
    save_button.pack(pady=10, padx=10, fill="x")

    # Load Lorebooks
    lorebooks = lorebook_manager.get_lorebooks_list()
    # Auto-select the first lorebook if available
    if lorebooks:
        first_lorebook = lorebooks[0]
        load_lorebook_details_func(
            lorebook=first_lorebook,
            notes_textbox=notes_textbox,
            misc_notes_textbox=misc_notes_textbox,
            filename_label=filename_label,
            created_label=created_label,
            last_modified_label=last_modified_label,
            lorebook_name_label=lorebook_name_label,
            images_frame=images_frame,
            linked_characters_frame=getattr(parent, "linked_characters_frame", None),
            selected_lorebook_id=getattr(parent, "selected_lorebook_id", None),
            set_selected_lorebook_id=lambda lorebook_id: setattr(parent, "selected_lorebook_id", lorebook_id),
            load_images_func=lorebook_manager.load_images,
            display_images_func=parent.display_images,
            get_linked_characters_func=lambda lorebook_id: get_linked_characters(db_path, lorebook_id),  # Pass db_path here
            display_linked_characters_func=display_linked_characters,
            handle_unlink_character_func=handle_unlink_character_func,
        )


        display_lorebooks_func(
            scrollable_lorebooks,
            lorebooks,
            on_select=lambda lorebook: load_lorebook_details_func(
                lorebook=lorebook,
                notes_textbox=notes_textbox,
                misc_notes_textbox=misc_notes_textbox,
                filename_label=filename_label,
                created_label=created_label,
                last_modified_label=last_modified_label,
                lorebook_name_label=lorebook_name_label,
                images_frame=images_frame,
                linked_characters_frame=getattr(parent, "linked_characters_frame", None),
                selected_lorebook_id=getattr(parent, "selected_lorebook_id", None),
                set_selected_lorebook_id=lambda lorebook_id: setattr(parent, "selected_lorebook_id", lorebook_id),
                load_images_func=lorebook_manager.load_images,
                display_images_func=parent.display_images,
                get_linked_characters_func=lambda lorebook_id: get_linked_characters(db_path, lorebook_id),  # Pass db_path here
                display_linked_characters_func=display_linked_characters,
                handle_unlink_character_func=handle_unlink_character_func,
            ),
        )

    # Search and filter lorebooks
    def filter_lorebooks(query):
        """Filter lorebooks based on the search query."""
        filtered_lorebooks = [
            lorebook
            for lorebook in lorebooks
            if query.lower() in Path(lorebook["filename"]).stem.lower()
        ]
        display_lorebooks_func(
            scrollable_lorebooks,
            filtered_lorebooks,
            on_select=lambda lorebook: load_lorebook_details_func(
                lorebook,
                notes_textbox,
                misc_notes_textbox,
                filename_label,
                created_label,
                last_modified_label,
                lorebook_name_label,
                images_frame,
            ),
        )

    search_var.trace_add("write", lambda *args: filter_lorebooks(search_var.get()))

    # Sort Lorebooks
    def sort_lorebooks(order):
        """Sort lorebooks based on the selected order."""
        sorted_lorebooks = lorebooks.copy()
        if order == "A - Z":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["filename"])
        elif order == "Z - A":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["filename"], reverse=True)
        elif order == "Newest":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["created_date"], reverse=True)
        elif order == "Oldest":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["created_date"])
        display_lorebooks_func(
            scrollable_lorebooks,
            sorted_lorebooks,
            on_select=lambda lorebook: load_lorebook_details_func(
                lorebook,
                notes_textbox,
                misc_notes_textbox,
                filename_label,
                created_label,
                last_modified_label,
                lorebook_name_label,
                images_frame,
            ),
        )


####### Lorebook Management Functions ###############
def refresh_lorebooks(
    lorebook_manager,
    display_lorebooks_func,
    load_lorebook_details_func,
    scrollable_lorebooks,
    notes_textbox,
    misc_notes_textbox,
    filename_label,
    created_label,
    last_modified_label,
    lorebook_name_label,
    images_frame
):
    """Refresh the lorebooks list and reload the selected lorebook."""
    # Reload lorebooks from the database
    updated_lorebooks = lorebook_manager.get_lorebooks_list()

    # Redisplay the lorebooks list
    display_lorebooks_func(
        scrollable_lorebooks,
        updated_lorebooks,
        on_select=lambda lorebook: load_lorebook_details_func(
            lorebook,
            notes_textbox,
            misc_notes_textbox,
            filename_label,
            created_label,
            last_modified_label,
            lorebook_name_label,
            images_frame,
        )
    )

    # Reload the details of the currently selected lorebook
    current_filename = filename_label.cget("text")
    current_lorebook = next((lb for lb in updated_lorebooks if lb["filename"] == current_filename), None)
    if current_lorebook:
        load_lorebook_details_func(
            current_lorebook,
            notes_textbox,
            misc_notes_textbox,
            filename_label,
            created_label,
            last_modified_label,
            lorebook_name_label,
            images_frame
        )


def display_lorebooks(frame, lorebooks, on_select, fg_color_default="#4b3e72", fg_color_selected="#d8bfd8"):
    """Display the list of lorebooks in the scrollable frame."""
    # Clear previous widgets
    for widget in frame.winfo_children():
        widget.destroy()

    # Keep track of buttons for dynamic updates
    button_map = {}

    def select_lorebook(lorebook, button):
        """Callback to handle selection of a lorebook."""
        # Reset all buttons to default appearance
        for btn in button_map.values():
            btn.configure(fg_color=fg_color_default, text_color="white")  # Reset to default color

        # Highlight the selected button
        button.configure(fg_color=fg_color_selected, text_color="black")

        # Call the provided on_select callback
        on_select(lorebook)

    def create_lorebook_button(lorebook):
        """Helper function to create a button for a lorebook."""
        display_name = Path(lorebook["filename"]).stem  # Strip extension
        button = ctk.CTkButton(
            frame,
            text=display_name,
            command=lambda: select_lorebook(lorebook, button)  # Correctly bind button to the lambda
        )
        button.pack(fill="x", padx=10, pady=5)
        button_map[lorebook["filename"]] = button

    # Add new buttons for each lorebook
    for lorebook in lorebooks:
        create_lorebook_button(lorebook)


def load_lorebook_details(
    lorebook,
    notes_textbox,
    misc_notes_textbox,
    filename_label,
    created_label,
    last_modified_label,
    lorebook_name_label,
    images_frame,
    linked_characters_frame,
    selected_lorebook_id,
    set_selected_lorebook_id,
    load_images_func,
    display_images_func,
    get_linked_characters_func,
    display_linked_characters_func,
    handle_unlink_character_func,
):
    """Load details of the selected lorebook into the modal."""
    display_name = Path(lorebook["filename"]).stem  # Strip extension
    lorebook_name_label.configure(text=display_name)  # Update the name label
    filename_label.configure(text=lorebook["filename"])
    notes_textbox.delete("1.0", "end")
    notes_textbox.insert("1.0", lorebook["notes"])
    misc_notes_textbox.delete("1.0", "end")
    misc_notes_textbox.insert("1.0", lorebook["misc_notes"])
    created_label.configure(text=f"Created Date: {lorebook['created_date']}")
    last_modified_label.configure(text=f"Last Modified Date: {lorebook['last_modified_date']}")

    # Set selected lorebook_id for image operations
    lorebook_id = lorebook.get("id")
    set_selected_lorebook_id(lorebook_id)

    # Load images
    if lorebook_id:
        images = load_images_func(lorebook_id)
        display_images_func(images_frame, images, lorebook)

    # Update linked characters display
    if linked_characters_frame and lorebook_id:
        linked_characters = get_linked_characters_func(lorebook_id)
        display_linked_characters_func(
            linked_characters_frame,
            linked_characters,
            handle_unlink_character_func,
            lorebook_id,
        )

def handle_lorebook_save(
    notes,
    misc_notes,
    filename,
    save_lorebook_changes_func,
    refresh_lorebooks_callback,
    show_message_func,
):
    """Handle saving lorebook changes and refresh the UI."""
    result = save_lorebook_changes_func(
        notes,
        misc_notes,
        filename,
        refresh_lorebooks_callback=refresh_lorebooks_callback,
    )

    # Display success or error message
    if "successfully" in result:
        show_message_func(result, "success")
    else:
        show_message_func(result, "error")


####### Lorebook Images Functions ###########
def display_images(
    frame,
    images,
    lorebook,
    create_thumbnail_func,
    edit_image_func,
    delete_image_func,
):
    """Display images with thumbnails, name, notes, and buttons in the scrollable frame."""
    for widget in frame.winfo_children():
        widget.destroy()

    # Extract the lorebook name and folder path
    lorebook_name = Path(lorebook["filename"]).stem  # Remove the extension
    lorebook_folder = Path("Lorebooks") / lorebook_name / "images"

    for image in images:
        image_id, image_name, image_note, created_date, last_modified_date = image
        image_frame = ctk.CTkFrame(frame)
        image_frame.pack(fill="x", padx=5, pady=5)

        # Construct the path to the image
        image_path = lorebook_folder / f"{image_name}.png"

        # Generate the thumbnail
        thumbnail = create_thumbnail_func(image_path)

        # Thumbnail and Text Container
        content_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
        content_frame.pack(side="left", fill="both", expand=True)

        # Thumbnail Display
        thumbnail_label = ctk.CTkLabel(content_frame, image=thumbnail, text="")
        thumbnail_label.image = thumbnail  # Keep reference to prevent garbage collection
        thumbnail_label.grid(row=0, column=0, rowspan=2, padx=5, pady=5)

        # Image Name
        image_label = ctk.CTkLabel(content_frame, text=image_name, font=("Arial", 14, "bold"))
        image_label.grid(row=0, column=1, sticky="w", padx=10)

        # Image Notes
        notes_label = ctk.CTkLabel(content_frame, text=f"Notes: {image_note}", font=("Arial", 12))
        notes_label.grid(row=1, column=1, sticky="w", padx=10)

        # Buttons
        buttons_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
        buttons_frame.pack(side="right", padx=10, pady=5)

        edit_button = ctk.CTkButton(
            buttons_frame,
            text="View/Edit",
            command=lambda img_id=image_id: edit_image_func(img_id, lorebook, frame)
        )
        edit_button.pack(pady=(0, 5))

        delete_button = ctk.CTkButton(
            buttons_frame,
            text="Delete",
            fg_color="red",
            command=lambda img_id=image_id: delete_image_func(img_id, frame)
        )
        delete_button.pack()


def add_image_modal(
    parent,
    lorebook_id,
    images_frame,
    browse_image_file_func,
    refresh_images_func,
    show_message_func,
):
    """Open a modal to add a new image."""
    if not lorebook_id:
        show_message_func("No lorebook selected to add an image.", "error")
        return

    # Create modal window
    modal = ctk.CTkToplevel(parent)
    modal.title("Add Image")
    modal.geometry("300x400")
    modal.transient(parent)
    modal.grab_set()

    # File Path
    path_label = ctk.CTkLabel(modal, text="Image Path:")
    path_label.pack(pady=5, padx=10, anchor="w")
    path_entry = ctk.CTkEntry(modal)
    path_entry.pack(pady=5, padx=10, fill="x")

    # Browse Button
    browse_button = ctk.CTkButton(
        modal, text="Browse", command=lambda: browse_image_file_func(path_entry)
    )
    browse_button.pack(pady=5, padx=10)

    # Image Name
    name_label = ctk.CTkLabel(modal, text="Image Name:")
    name_label.pack(pady=5, padx=10, anchor="w")
    name_entry = ctk.CTkEntry(modal)
    name_entry.pack(pady=5, padx=10, fill="x")

    # Image Notes
    notes_label = ctk.CTkLabel(modal, text="Image Notes:")
    notes_label.pack(pady=5, padx=10, anchor="w")
    notes_textbox = ctk.CTkTextbox(modal, height=100)
    notes_textbox.pack(pady=5, padx=10, fill="x")

    # Save Button
    save_button = ctk.CTkButton(
        modal,
        text="Save Image",
        command=lambda: save_image_func(
            lorebook_id,
            name_entry.get(),  # Image name
            notes_textbox.get("1.0", "end").strip(),  # Image note
            path_entry.get(),  # File path
            modal,
            lambda: refresh_images_func(images_frame, lorebook_id),  # Refresh images callback
            show_message_func,  # Message display function
        ),
    )
    save_button.pack(pady=10, padx=10)


import shutil

def save_image_func(
    lorebook_id,
    image_name,
    image_note,
    file_path,
    modal,
    refresh_images_callback,
    show_message_func,
):
    """Save a new image to the database."""
    if not lorebook_id or not image_name or not file_path:
        show_message_func("Lorebook ID, image name, and file path are required.", "error")
        return

    # Check for duplicate image name
    if not is_image_name_unique(db_path, image_name, lorebook_id):
        show_message_func("An image with this name already exists in the lorebook.", "error")
        return

    # Get current timestamp for created_date and last_modified_date
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fetch the lorebook filename to use as the folder name
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("SELECT filename FROM lorebooks WHERE id = ?", (lorebook_id,))
    lorebook_data = cursor.fetchone()
    connection.close()

    if not lorebook_data:
        show_message_func("Failed to find the lorebook in the database.", "error")
        return

    lorebook_filename = Path(lorebook_data[0]).stem  # Strip file extension

    # Construct the lorebook folder path
    lorebook_folder = Path("Lorebooks") / lorebook_filename / "images"
    lorebook_folder.mkdir(parents=True, exist_ok=True)

    try:
        # Insert the new image with timestamps
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO lorebook_images (
                lorebook_id, image_name, image_note, created_date, last_modified_date
            ) VALUES (?, ?, ?, ?, ?)
        """, (lorebook_id, image_name, image_note, current_timestamp, current_timestamp))
        connection.commit()

        # Copy the image file to the lorebook's folder
        new_file_path = lorebook_folder / f"{image_name}.png"
        shutil.copy(file_path, new_file_path)

        show_message_func("Image added successfully.", "success")
        modal.destroy()  # Close the modal after saving
        refresh_images_callback()  # Refresh the images in the UI
    except sqlite3.Error as e:
        show_message_func(f"Failed to save the image: {e}", "error")
    except shutil.Error as e:
        show_message_func(f"Failed to copy the image: {e}", "error")
    finally:
        connection.close()


def edit_image(
    parent,
    image_id,
    lorebook,
    images_frame,
    selected_lorebook_id,
    get_image_details_func,
    save_image_changes_func,
    show_message_func,
):
    """Open a modal to edit image details."""
    if not selected_lorebook_id:
        show_message_func("No lorebook selected to edit the image.", "error")
        return

    # Fetch image details
    image_details = get_image_details_func(image_id)
    if not image_details:
        show_message_func("Failed to retrieve image details.", "error")
        return

    image_name, image_note, created_date, last_modified_date = image_details

    # Determine the image path
    lorebook_name = Path(lorebook["filename"]).stem  # Remove .json from the filename
    lorebook_folder = Path("Lorebooks") / lorebook_name / "images"
    image_path = lorebook_folder / f"{image_name}.png"  # Construct the image path

    # Create a modal window
    modal = ctk.CTkToplevel(parent)
    modal.title("Edit Image")
    modal.geometry("400x600")  # Adjust height to accommodate the image
    modal.transient(parent)
    modal.grab_set()

    # Image Name
    name_label = ctk.CTkLabel(modal, text="Image Name:")
    name_label.pack(pady=5, padx=10, anchor="w")
    name_entry = ctk.CTkEntry(modal)
    name_entry.insert(0, image_name)
    name_entry.pack(pady=5, padx=10, fill="x")

    # Image Notes
    notes_label = ctk.CTkLabel(modal, text="Image Notes:")
    notes_label.pack(pady=5, padx=10, anchor="w")
    notes_textbox = ctk.CTkTextbox(modal, height=100)
    notes_textbox.insert("1.0", image_note)
    notes_textbox.pack(pady=5, padx=10, fill="x")

    # Save Button
    save_button = ctk.CTkButton(
        modal,
        text="Save Changes",
        command=lambda: save_image_changes_func(
            image_id,
            name_entry.get().strip(),
            notes_textbox.get("1.0", "end").strip(),
            modal,
            images_frame,
            lorebook,
        ),
    )
    save_button.pack(pady=10, padx=10)

    # Display Image Section
    try:
        print(f"Looking for image at: {image_path}")  # Debugging: Print the constructed path
        if image_path.exists():  # Ensure the image exists
            img = Image.open(image_path)
            img.thumbnail((300, 300))  # Resize to fit within 300x300
            ctk_image = ctk.CTkImage(img, size=(300, img.height))

            image_label = ctk.CTkLabel(modal, image=ctk_image, text="")
            image_label.image = ctk_image  # Keep a reference to prevent garbage collection
            image_label.pack(pady=(10, 10))  # Add some spacing around the image
        else:
            error_label = ctk.CTkLabel(modal, text="Image not found.", text_color="red")
            error_label.pack(pady=(10, 10))
    except Exception as e:
        print(f"Error loading image: {e}")
        error_label = ctk.CTkLabel(modal, text="Failed to load image.", text_color="red")
        error_label.pack(pady=(10, 10))

def refresh_images(
    images_frame,
    lorebook_id,
    lorebook,
    get_lorebooks_list_func,
    load_images_func,
    display_images_func,
    show_message_func,
):
    """Refresh the images displayed in the frame for the selected lorebook."""
    if lorebook_id:
        if not lorebook:
            # Fetch the lorebook object if not provided
            lorebook = next(
                (lb for lb in get_lorebooks_list_func() if lb["id"] == lorebook_id),
                None,
            )
        if not lorebook:
            show_message_func("Failed to fetch the lorebook details.", "error")
            return

        images = load_images_func(lorebook_id)
        display_images_func(images_frame, images, lorebook)
        show_message_func("Image list updated successfully!", "success")


def save_image_changes(
    image_id,
    new_image_name,
    new_image_note,
    modal,
    images_frame,
    lorebook,
    get_image_details_func,
    update_image_details_func,
    refresh_images_func,
    selected_lorebook_id,
    show_message_func,
):
    """Save changes to an image, including renaming the file if necessary."""
    if not new_image_name:
        show_message_func("Image name cannot be empty.", "error")
        return

    # Fetch the existing image details
    image_details = get_image_details_func(image_id)
    if not image_details:
        show_message_func("Failed to retrieve image details.", "error")
        return

    old_image_name, _, _, _ = image_details

    # Check for duplicate image name, excluding the current image being edited
    if new_image_name != old_image_name and not is_image_name_unique(db_path, new_image_name, selected_lorebook_id, exclude_image_id=image_id):
        show_message_func("An image with this name already exists in the lorebook.", "error")
        return

    # Determine the lorebook folder and file paths
    lorebook_name = Path(lorebook["filename"]).stem  # Remove .json from the filename
    lorebook_folder = Path("Lorebooks") / lorebook_name / "images"
    old_image_path = lorebook_folder / f"{old_image_name}.png"
    new_image_path = lorebook_folder / f"{new_image_name}.png"

    # Rename the file if the name has changed
    if old_image_name != new_image_name:
        try:
            if old_image_path.exists():
                old_image_path.rename(new_image_path)
                print(f"Renamed image from {old_image_path} to {new_image_path}")
            else:
                print(f"Old image file not found: {old_image_path}")
        except Exception as e:
            print(f"Error renaming image file: {e}")
            show_message_func("Failed to rename the image file. Please check file permissions.", "error")
            return

    # Update the database
    success = update_image_details_func(image_id, new_image_name, new_image_note)
    if success:
        show_message_func("Image updated successfully.", "success")
        modal.destroy()
        # Refresh the image list
        refresh_images_func(images_frame, selected_lorebook_id, lorebook)
    else:
        show_message_func("Failed to update image.", "error")



def delete_image(
    image_id,
    images_frame,
    selected_lorebook_id,
    get_lorebooks_list_func,
    delete_image_func,
    refresh_images_func,
    show_message_func,
    askyesno_func,
):
    """Delete an image from the selected lorebook."""
    if not selected_lorebook_id:
        show_message_func("No lorebook selected.", "error")
        return

    # Confirm deletion
    confirm = askyesno_func("Delete Image", "Are you sure you want to delete this image? This action cannot be undone.")
    if not confirm:
        return

    # Call LorebookManager to delete the image
    success = delete_image_func(image_id, selected_lorebook_id)
    if success:
        show_message_func("Image deleted successfully.", "success")
        # Pass the current lorebook to refresh the images list
        lorebook = next(
            (lb for lb in get_lorebooks_list_func() if lb["id"] == selected_lorebook_id),
            None,
        )
        refresh_images_func(images_frame, selected_lorebook_id, lorebook)
    else:
        show_message_func("Failed to delete the image.", "error")

def browse_image_file(entry_widget):
    """Open a file dialog to select an image and update the entry widget."""
    file_path = askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
    if file_path:
        entry_widget.delete(0, "end")
        entry_widget.insert(0, file_path)

def is_image_name_unique(db_path, image_name, lorebook_id, exclude_image_id=None):
    """Check if the image name is unique within the specified lorebook."""
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    if exclude_image_id:
        # Exclude the current image ID from the uniqueness check
        cursor.execute("""
            SELECT COUNT(*) FROM lorebook_images
            WHERE image_name = ? AND lorebook_id = ? AND id != ?
        """, (image_name, lorebook_id, exclude_image_id))
    else:
        cursor.execute("""
            SELECT COUNT(*) FROM lorebook_images
            WHERE image_name = ? AND lorebook_id = ?
        """, (image_name, lorebook_id))

    is_unique = cursor.fetchone()[0] == 0
    connection.close()
    return is_unique



####### Character Linking Functions #########
def open_link_character_modal_for_lorebook(
    parent,
    lorebook_id,
    create_thumbnail,
    get_character_list,
    linked_character_ids_func,
    handle_link_character_func,
    align_modal_top_left
):
    """Open a modal to search and link characters to a lorebook."""
    if not lorebook_id:
        parent.show_message("No lorebook selected to link characters.", "error")
        return

    # Open modal
    link_character_window = ctk.CTkToplevel(parent)
    link_character_window.title("Link Characters to Lorebook")
    link_character_window.geometry("400x500")
    link_character_window.transient(parent)
    link_character_window.grab_set()
    link_character_window.focus_set()

    # Align the modal relative to the parent window
    align_modal_top_left(link_character_window)

    # Search Bar
    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(
        link_character_window,
        textvariable=search_var,
        placeholder_text="Search characters...",
        width=300
    )
    search_entry.pack(pady=(10, 5), padx=10)

    # Scrollable Frame for Character List
    scrollable_frame = ctk.CTkScrollableFrame(link_character_window, height=350)
    scrollable_frame.pack(fill="both", expand=True, padx=10, pady=5)

    # Pagination Controls
    nav_frame = ctk.CTkFrame(link_character_window)
    nav_frame.pack(fill="x", pady=(5, 10))

    prev_button = ctk.CTkButton(nav_frame, text="Previous", command=lambda: navigate_page(-1))
    prev_button.pack(side="left", padx=5)

    next_button = ctk.CTkButton(nav_frame, text="Next", command=lambda: navigate_page(1))
    next_button.pack(side="right", padx=5)

    page_label = ctk.CTkLabel(nav_frame, text="Page 1")
    page_label.pack(side="left", padx=5)

    # Fetch all characters and setup pagination
    all_characters = get_character_list()
    linked_character_ids = linked_character_ids_func(lorebook_id)
    filtered_characters = [char for char in all_characters if char["id"] not in linked_character_ids]
    items_per_page = 10
    current_page = [0]

    def update_modal_display():
        """Update the modal with the filtered and paginated character list."""
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
            thumbnail = create_thumbnail(char["image_path"])
            thumbnail_label = ctk.CTkLabel(char_frame, image=thumbnail, text="")
            thumbnail_label.image = thumbnail  # Prevent garbage collection
            thumbnail_label.grid(row=0, column=0, padx=5, sticky="w")

            # Character Name
            name_label = ctk.CTkLabel(char_frame, text=char["name"], anchor="w", font=("Arial", 12, "bold"))
            name_label.grid(row=0, column=1, padx=5, sticky="w")

            # Link Button
            link_button = ctk.CTkButton(
                char_frame,
                text="Link",
                command=lambda char_id=char["id"]: handle_link_character_func(char_id, lorebook_id)
            )
            link_button.grid(row=0, column=2, padx=5, sticky="e")

        # Update page label
        page_label.configure(text=f"Page {current_page[0] + 1} of {len(filtered_characters) // items_per_page + 1}")
        # Reset scrollbar to top
        scrollable_frame._parent_canvas.yview_moveto(0)

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
            char for char in all_characters if char["id"] not in linked_character_ids and query in char["name"].lower()
        ]
        current_page[0] = 0  # Reset to the first page
        update_modal_display()

    # Bind the search bar to the filter function
    search_var.trace_add("write", filter_characters)

    # Display the initial character list
    update_modal_display()

def display_linked_characters(frame, linked_characters, handle_unlink_character_func, lorebook_id):
    """Display linked characters in the scrollable frame."""
    for widget in frame.winfo_children():
        widget.destroy()

    for char in linked_characters:
        char_frame = ctk.CTkFrame(frame, corner_radius=5)
        char_frame.pack(pady=5, padx=5, fill="x")

        # Character Name
        name_label = ctk.CTkLabel(char_frame, text=char["name"], anchor="w", font=("Arial", 12, "bold"))
        name_label.pack(side="left", padx=10)

        # Unlink Button
        unlink_button = ctk.CTkButton(
            char_frame,
            text="Unlink",
            command=lambda char_id=char["id"]: handle_unlink_character_func(char_id, lorebook_id)
        )
        unlink_button.pack(side="right", padx=10)

def get_linked_characters(db_path, lorebook_id):
    """Retrieve characters linked to the lorebook."""
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute("""
        SELECT c.id, c.name
        FROM characters c
        JOIN lorebook_character_links lcl ON c.id = lcl.character_id
        WHERE lcl.lorebook_id = ?
    """, (lorebook_id,))
    characters = cursor.fetchall()
    connection.close()
    return [{"id": char[0], "name": char[1]} for char in characters]

def link_character_to_lorebook(db_path, char_id, lorebook_id):
    """Link a character to a lorebook in the database."""
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        # Check if the character is already linked to the lorebook
        cursor.execute("""
            SELECT COUNT(*)
            FROM lorebook_character_links
            WHERE lorebook_id = ? AND character_id = ?
        """, (lorebook_id, char_id))
        already_linked = cursor.fetchone()[0] > 0

        if already_linked:
            connection.close()
            return {"status": "error", "message": "Character is already linked to this lorebook."}

        # Insert the new link if not already linked
        cursor.execute("""
            INSERT INTO lorebook_character_links (lorebook_id, character_id)
            VALUES (?, ?)
        """, (lorebook_id, char_id))
        connection.commit()
        connection.close()
        return {"status": "success", "message": "Character linked successfully!"}
    except sqlite3.Error as e:
        print(f"Error linking character to lorebook: {e}")
        return {"status": "error", "message": f"Failed to link character to lorebook: {e}"}


def unlink_character_from_lorebook(db_path, char_id, lorebook_id):
    """Unlink a character from a lorebook."""
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute("""
            DELETE FROM lorebook_character_links
            WHERE lorebook_id = ? AND character_id = ?
        """, (lorebook_id, char_id))
        connection.commit()
        connection.close()
        if cursor.rowcount > 0:
            return {"status": "success", "message": "Character unlinked successfully!"}
        else:
            return {"status": "error", "message": "Failed to unlink character."}
    except sqlite3.Error as e:
        print(f"Error unlinking character from lorebook: {e}")
        return {"status": "error", "message": f"Failed to unlink character from lorebook: {e}"}
