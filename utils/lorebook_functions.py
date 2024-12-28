import customtkinter as ctk
from tkinter.filedialog import askopenfilename
from pathlib import Path
from datetime import datetime

def open_lorebooks_modal(parent, lorebook_manager, display_lorebooks, load_lorebook_details, handle_lorebook_save, show_message):
    """Open a modal to manage lorebooks."""
    lorebooks_modal = ctk.CTkToplevel(parent)
    lorebooks_modal.title("Manage Lorebooks")
    lorebooks_modal.geometry("1200x700")
    lorebooks_modal.transient(parent)
    lorebooks_modal.grab_set()

    # Configure layout
    lorebooks_modal.grid_columnconfigure(0, weight=1)  # Left column for list
    lorebooks_modal.grid_columnconfigure(1, weight=2)  # Right column for details
    lorebooks_modal.grid_rowconfigure(0, weight=1)

    # Left Column - Lorebooks List
    list_frame = ctk.CTkFrame(lorebooks_modal, corner_radius=0)
    list_frame.grid(row=0, column=0, sticky="nswe", padx=10, pady=10)

    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(
        list_frame,
        textvariable=search_var,
        placeholder_text="Search lorebooks...",
        width=300,
    )
    search_entry.pack(pady=(10, 5), padx=10)

    sort_var = ctk.StringVar(value="A - Z")
    sort_dropdown = ctk.CTkOptionMenu(
        list_frame,
        values=["A - Z", "Z - A", "Newest", "Oldest"],
        variable=sort_var,
        command=lambda order: sort_lorebooks(order, lorebooks, scrollable_lorebooks, display_lorebooks, load_lorebook_details)
    )
    sort_dropdown.pack(pady=(5, 10), padx=10)

    scrollable_lorebooks = ctk.CTkScrollableFrame(list_frame)
    scrollable_lorebooks.pack(fill="both", expand=True, padx=10, pady=10)

    # Right Column - Details
    details_frame = ctk.CTkFrame(lorebooks_modal, corner_radius=0)
    details_frame.grid(row=0, column=1, sticky="nswe", padx=10, pady=10)

    # Add a label at the top of the details panel for the lorebook name
    lorebook_name_label = ctk.CTkLabel(details_frame, text="Select a Lorebook", font=("Arial", 16, "bold"))
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

    # Scrollable frame for images
    images_frame = ctk.CTkScrollableFrame(images_tab)
    images_frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Add image button
    add_image_button = ctk.CTkButton(
        images_tab,
        text="Add Image",
        command=lambda: show_message("Add Image functionality not yet implemented.", "info")
    )
    add_image_button.pack(pady=(10, 0))

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
        command=lambda: handle_lorebook_save(
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
            images_frame
        )
    )
    save_button.pack(pady=10, padx=10, fill="x")

    # Load Lorebooks
    lorebooks = lorebook_manager.get_lorebooks_list()
    display_lorebooks(
        scrollable_lorebooks, lorebooks,
        on_select=lambda lorebook: load_lorebook_details(
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

    # Sort and Filter
    def sort_lorebooks(order, lorebooks, scrollable_lorebooks, display_lorebooks, load_lorebook_details):
        sorted_lorebooks = sorted(
            lorebooks,
            key=lambda x: x["filename"],
            reverse=(order in ["Z - A", "Newest"])
        )
        display_lorebooks(
            scrollable_lorebooks,
            sorted_lorebooks,
            on_select=lambda lorebook: load_lorebook_details(
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

    def filter_lorebooks(query):
        filtered_lorebooks = [
            lorebook for lorebook in lorebooks
            if query.lower() in Path(lorebook["filename"]).stem.lower()
        ]
        display_lorebooks(
            scrollable_lorebooks,
            filtered_lorebooks,
            on_select=lambda lorebook: load_lorebook_details(
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

    search_var.trace_add("write", lambda *args: filter_lorebooks(search_var.get()))


    def sort_lorebooks(order, lorebooks, display_lorebooks, scrollable_lorebooks, load_lorebook_details, details_args):
        """
        Sort lorebooks based on the selected order and refresh the display.

        Args:
            order (str): The sorting order ("A - Z", "Z - A", "Newest", "Oldest").
            lorebooks (list): The list of lorebooks.
            display_lorebooks (function): Function to display lorebooks.
            scrollable_lorebooks (ctk.CTkScrollableFrame): The frame to display sorted lorebooks.
            load_lorebook_details (function): Function to load lorebook details.
            details_args (dict): Arguments to pass for loading lorebook details.
        """
        if order == "A - Z":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["filename"])
        elif order == "Z - A":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["filename"], reverse=True)
        elif order == "Newest":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["created_date"], reverse=True)
        elif order == "Oldest":
            sorted_lorebooks = sorted(lorebooks, key=lambda x: x["created_date"])
        else:
            sorted_lorebooks = lorebooks.copy()

        display_lorebooks(
            scrollable_lorebooks,
            sorted_lorebooks,
            on_select=lambda lorebook: load_lorebook_details(lorebook, **details_args)
        )


    def filter_lorebooks(query, lorebooks, display_lorebooks, scrollable_lorebooks, load_lorebook_details, details_args):
        """
        Filter lorebooks based on the search query and refresh the display.

        Args:
            query (str): The search query.
            lorebooks (list): The list of lorebooks.
            display_lorebooks (function): Function to display lorebooks.
            scrollable_lorebooks (ctk.CTkScrollableFrame): The frame to display filtered lorebooks.
            load_lorebook_details (function): Function to load lorebook details.
            details_args (dict): Arguments to pass for loading lorebook details.
        """
        filtered_lorebooks = [
            lorebook for lorebook in lorebooks
            if query.lower() in Path(lorebook["filename"]).stem.lower()
        ]

        display_lorebooks(
            scrollable_lorebooks,
            filtered_lorebooks,
            on_select=lambda lorebook: load_lorebook_details(lorebook, **details_args)
        )

def refresh_lorebooks(
    scrollable_lorebooks,
    notes_textbox,
    misc_notes_textbox,
    filename_label,
    created_label,
    last_modified_label,
    lorebook_name_label,
    images_frame,
    lorebook_manager,
    display_lorebooks,
    load_lorebook_details
):
    """
    Refresh the lorebooks list and reload the selected lorebook.

    Args:
        scrollable_lorebooks (ctk.CTkScrollableFrame): The scrollable frame to display lorebooks.
        notes_textbox (ctk.CTkTextbox): The textbox for lorebook notes.
        misc_notes_textbox (ctk.CTkTextbox): The textbox for miscellaneous notes.
        filename_label (ctk.CTkLabel): The label displaying the filename.
        created_label (ctk.CTkLabel): The label displaying the created date.
        last_modified_label (ctk.CTkLabel): The label displaying the last modified date.
        lorebook_name_label (ctk.CTkLabel): The label displaying the lorebook name.
        images_frame (ctk.CTkScrollableFrame): The frame displaying images.
        lorebook_manager (object): The manager to handle lorebook operations.
        display_lorebooks (function): Function to display the lorebooks.
        load_lorebook_details (function): Function to load lorebook details.
    """
    # Reload lorebooks from the database
    updated_lorebooks = lorebook_manager.get_lorebooks_list()

    # Redisplay the lorebooks list
    display_lorebooks(
        scrollable_lorebooks,
        updated_lorebooks,
        on_select=lambda lorebook: load_lorebook_details(
            lorebook,
            notes_textbox=notes_textbox,
            misc_notes_textbox=misc_notes_textbox,
            filename_label=filename_label,
            created_label=created_label,
            last_modified_label=last_modified_label,
            lorebook_name_label=lorebook_name_label,
            images_frame=images_frame
        )
    )

    # Reload the details of the currently selected lorebook
    current_filename = filename_label.cget("text")
    current_lorebook = next((lb for lb in updated_lorebooks if lb["filename"] == current_filename), None)
    if current_lorebook:
        load_lorebook_details(
            current_lorebook,
            notes_textbox=notes_textbox,
            misc_notes_textbox=misc_notes_textbox,
            filename_label=filename_label,
            created_label=created_label,
            last_modified_label=last_modified_label,
            lorebook_name_label=lorebook_name_label,
            images_frame=images_frame
        )


def display_lorebooks(frame, lorebooks, on_select):
    """
    Display the list of lorebooks in the scrollable frame.

    Args:
        frame (ctk.CTkScrollableFrame): The frame where lorebooks will be displayed.
        lorebooks (list): List of lorebooks to display.
        on_select (function): Callback function to execute when a lorebook is selected.
    """
    # Clear previous widgets
    for widget in frame.winfo_children():
        widget.destroy()

    # Add new buttons for each lorebook
    for lorebook in lorebooks:
        display_name = Path(lorebook["filename"]).stem  # Strip extension
        button = ctk.CTkButton(
            frame,
            text=display_name,
            command=lambda lb=lorebook: on_select(lb)
        )
        button.pack(fill="x", padx=10, pady=5)


def load_lorebook_details(
    lorebook,
    notes_textbox,
    misc_notes_textbox,
    filename_label,
    created_label,
    last_modified_label,
    lorebook_name_label,
    images_frame,
    lorebook_manager,
    display_images
):
    """
    Load details of the selected lorebook into the modal.

    Args:
        lorebook (dict): The lorebook data to load.
        notes_textbox (ctk.CTkTextbox): Textbox to display lorebook notes.
        misc_notes_textbox (ctk.CTkTextbox): Textbox to display miscellaneous notes.
        filename_label (ctk.CTkLabel): Label to display the filename.
        created_label (ctk.CTkLabel): Label to display the created date.
        last_modified_label (ctk.CTkLabel): Label to display the last modified date.
        lorebook_name_label (ctk.CTkLabel): Label to display the lorebook name.
        images_frame (ctk.CTkScrollableFrame): Frame to display images.
        lorebook_manager (object): Manager to handle lorebook-related operations.
        display_images (function): Function to display the images in the frame.
    """
    display_name = Path(lorebook["filename"]).stem  # Strip extension
    lorebook_name_label.configure(text=display_name)  # Update the name label
    filename_label.configure(text=lorebook["filename"])
    
    # Update notes
    notes_textbox.delete("1.0", "end")
    notes_textbox.insert("1.0", lorebook["notes"])
    
    # Update miscellaneous notes
    misc_notes_textbox.delete("1.0", "end")
    misc_notes_textbox.insert("1.0", lorebook["misc_notes"])
    
    # Update metadata
    created_label.configure(text=f"Created Date: {lorebook['created_date']}")
    last_modified_label.configure(text=f"Last Modified Date: {lorebook['last_modified_date']}")

    # Load images if lorebook ID is available
    lorebook_id = lorebook.get("id")
    if lorebook_id:
        images = lorebook_manager.load_images(lorebook_id)
        display_images(images_frame, images, lorebook)


def display_images(
    frame,
    images,
    lorebook,
    create_thumbnail,
    edit_image_callback,
    delete_image_callback
):
    """
    Display images with thumbnails, names, notes, and buttons in the scrollable frame.

    Args:
        frame (ctk.CTkScrollableFrame): The frame to populate with image widgets.
        images (list): List of image details (id, name, notes, created_date, last_modified_date).
        lorebook (dict): The lorebook containing the images.
        create_thumbnail (function): Function to generate a thumbnail for an image.
        edit_image_callback (function): Callback function for editing an image.
        delete_image_callback (function): Callback function for deleting an image.
    """
    # Clear existing widgets
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
        thumbnail = create_thumbnail(image_path)

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
            command=lambda img_id=image_id: edit_image_callback(img_id, lorebook, frame)
        )
        edit_button.pack(pady=(0, 5))

        delete_button = ctk.CTkButton(
            buttons_frame,
            text="Delete",
            fg_color="red",
            command=lambda img_id=image_id: delete_image_callback(img_id, frame)
        )
        delete_button.pack()

def add_image_modal(
    lorebook_id,
    images_frame,
    browse_image_file_callback,
    save_image_callback,
    refresh_images_callback,
    show_message_callback
):
    """
    Open a modal to add a new image to a lorebook.

    Args:
        lorebook_id (int): The ID of the selected lorebook.
        images_frame (ctk.CTkScrollableFrame): Frame to refresh after saving the image.
        browse_image_file_callback (function): Callback to open file browser for image selection.
        save_image_callback (function): Callback to save the image to the lorebook.
        refresh_images_callback (function): Callback to refresh the image list.
        show_message_callback (function): Callback to display messages to the user.
    """
    if not lorebook_id:
        show_message_callback("No lorebook selected to add an image.", "error")
        return

    # Create modal window
    modal = ctk.CTkToplevel()
    modal.title("Add Image")
    modal.geometry("300x400")
    modal.transient(modal.master)
    modal.grab_set()

    # File Path
    path_label = ctk.CTkLabel(modal, text="Image Path:")
    path_label.pack(pady=5, padx=10, anchor="w")
    path_entry = ctk.CTkEntry(modal)
    path_entry.pack(pady=5, padx=10, fill="x")

    # Browse Button
    browse_button = ctk.CTkButton(
        modal, text="Browse", command=lambda: browse_image_file_callback(path_entry)
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
        command=lambda: save_image_callback(
            lorebook_id,
            name_entry.get(),
            notes_textbox.get("1.0", "end").strip(),
            path_entry.get(),
            modal,
            lambda: refresh_images_callback(images_frame, lorebook_id)
        )
    )
    save_button.pack(pady=10, padx=10)
def handle_lorebook_save(
    notes,
    misc_notes,
    filename,
    refresh_lorebooks_callback,
    show_message_callback,
):
    """
    Handle saving lorebook changes and refresh the UI.

    Args:
        notes (str): Notes of the lorebook.
        misc_notes (str): Miscellaneous notes of the lorebook.
        filename (str): Filename of the lorebook.
        refresh_lorebooks_callback (function): Callback to refresh the lorebooks list.
        show_message_callback (function): Callback to display messages to the user.
    """
    result = LorebookManager.save_lorebook_changes(
        notes,
        misc_notes,
        filename,
        refresh_lorebooks_callback=refresh_lorebooks_callback
    )

    # Display success or error message
    if "successfully" in result:
        show_message_callback(result, "success")
    else:
        show_message_callback(result, "error")


def refresh_images(
    images_frame,
    lorebook_id,
    lorebook_manager,
    display_images_callback,
    show_message_callback,
    lorebook=None
):
    """
    Refresh the images displayed in the frame for the selected lorebook.

    Args:
        images_frame (ctk.CTkScrollableFrame): Frame to display images.
        lorebook_id (int): ID of the selected lorebook.
        lorebook_manager (LorebookManager): Instance of the lorebook manager to interact with data.
        display_images_callback (function): Callback to display images in the UI.
        show_message_callback (function): Callback to display messages to the user.
        lorebook (dict, optional): Lorebook object if already fetched. Defaults to None.
    """
    if lorebook_id:
        if not lorebook:
            # Fetch the lorebook object if not provided
            lorebook = next(
                (lb for lb in lorebook_manager.get_lorebooks_list() if lb["id"] == lorebook_id),
                None
            )
        if not lorebook:
            show_message_callback("Failed to fetch the lorebook details.", "error")
            return

        # Load images and update the display
        images = lorebook_manager.load_images(lorebook_id)
        display_images_callback(images_frame, images, lorebook)
        show_message_callback("Image list updated successfully!", "success")
def delete_image(
    image_id,
    selected_lorebook_id,
    images_frame,
    lorebook_manager,
    refresh_images_callback,
    show_message_callback
):
    """
    Delete an image from the selected lorebook.

    Args:
        image_id (int): ID of the image to delete.
        selected_lorebook_id (int): ID of the selected lorebook.
        images_frame (ctk.CTkScrollableFrame): Frame to refresh after deletion.
        lorebook_manager (LorebookManager): Instance of the lorebook manager.
        refresh_images_callback (function): Callback to refresh the images list.
        show_message_callback (function): Callback to display messages to the user.
    """
    if not selected_lorebook_id:
        show_message_callback("No lorebook selected.", "error")
        return

    # Confirm deletion
    confirm = askyesno("Delete Image", "Are you sure you want to delete this image? This action cannot be undone.")
    if not confirm:
        return

    # Call LorebookManager to delete the image
    success = lorebook_manager.delete_image(image_id, selected_lorebook_id)
    if success:
        show_message_callback("Image deleted successfully.", "success")
        # Pass the current lorebook to refresh the images list
        lorebook = next(
            (lb for lb in lorebook_manager.get_lorebooks_list() if lb["id"] == selected_lorebook_id),
            None
        )
        if lorebook:
            refresh_images_callback(images_frame, selected_lorebook_id, lorebook)
    else:
        show_message_callback("Failed to delete the image.", "error")


def browse_image_file(entry_widget):
    """
    Open a file dialog to select an image and update the entry widget.

    Args:
        entry_widget (ctk.CTkEntry): Entry widget to update with the selected file path.
    """
    file_path = askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
    if file_path:
        entry_widget.delete(0, "end")
        entry_widget.insert(0, file_path)


def edit_image(
    image_id,
    lorebook,
    images_frame,
    lorebook_manager,
    save_image_changes_callback,
    show_message_callback,
):
    """
    Open a modal to edit image details.

    Args:
        image_id (int): ID of the image to edit.
        lorebook (dict): Details of the lorebook containing the image.
        images_frame (ctk.CTkScrollableFrame): Frame to refresh after editing.
        lorebook_manager (LorebookManager): Instance of the lorebook manager.
        save_image_changes_callback (function): Callback to save image changes.
        show_message_callback (function): Callback to display messages to the user.
    """
    if not lorebook:
        show_message_callback("No lorebook selected to edit the image.", "error")
        return

    # Fetch image details
    image_details = lorebook_manager.get_image_details(image_id)
    if not image_details:
        show_message_callback("Failed to retrieve image details.", "error")
        return

    image_name, image_note, created_date, last_modified_date = image_details

    # Determine the image path
    lorebook_name = Path(lorebook["filename"]).stem  # Remove .json from the filename
    lorebook_folder = Path("Lorebooks") / lorebook_name / "images"
    image_path = lorebook_folder / f"{image_name}.png"  # Construct the image path

    # Create a modal window
    modal = ctk.CTkToplevel()
    modal.title("Edit Image")
    modal.geometry("400x600")  # Adjust height to accommodate the image
    modal.transient(None)
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
        command=lambda: save_image_changes_callback(
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
        if Path(image_path).exists():  # Ensure the image exists
            from PIL import Image

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
def save_image_changes(
    image_id,
    new_image_name,
    new_image_note,
    modal,
    images_frame,
    lorebook,
    lorebook_manager,
    refresh_images_callback,
    show_message_callback,
):
    """
    Save changes to an image, including renaming the file if necessary.

    Args:
        image_id (int): ID of the image to update.
        new_image_name (str): New name for the image.
        new_image_note (str): Updated notes for the image.
        modal (ctk.CTkToplevel): The modal window to close after saving.
        images_frame (ctk.CTkScrollableFrame): Frame to refresh after saving.
        lorebook (dict): Details of the lorebook containing the image.
        lorebook_manager (LorebookManager): Instance of the lorebook manager.
        refresh_images_callback (function): Callback to refresh the images in the UI.
        show_message_callback (function): Callback to display messages to the user.
    """
    if not new_image_name:
        show_message_callback("Image name cannot be empty.", "error")
        return

    # Fetch the existing image details
    image_details = lorebook_manager.get_image_details(image_id)
    if not image_details:
        show_message_callback("Failed to retrieve image details.", "error")
        return

    old_image_name, _, _, _ = image_details

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
                show_message_callback("Original image file not found. Rename failed.", "error")
                return
        except Exception as e:
            print(f"Error renaming image file: {e}")
            show_message_callback("Failed to rename the image file. Please check file permissions.", "error")
            return

    # Update the database
    success = lorebook_manager.update_image_details(image_id, new_image_name, new_image_note)
    if success:
        show_message_callback("Image updated successfully.", "success")
        modal.destroy()
        # Refresh the image list
        refresh_images_callback(images_frame, lorebook.get("id"), lorebook)
    else:
        show_message_callback("Failed to update image.", "error")