import customtkinter as ctk

class BaseModal(ctk.CTkToplevel):
    def __init__(self, parent, title="Modal", width=600, height=400):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.transient(parent)  # Make modal a child of the parent
        self.grab_set()         # Block interaction with the parent

        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Message banner
        self.message_banner = ctk.CTkLabel(self, text="", fg_color="#FFCDD2", height=30, text_color="black", corner_radius=5)
        self.message_banner.pack(fill="x", padx=10, pady=5)
        self.message_banner.pack_forget()  # Hidden initially

        # Scrollable content frame
        self.content_frame = ctk.CTkScrollableFrame(self)
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Footer buttons frame
        self.footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.footer_frame.pack(fill="x", padx=10, pady=(0, 10))

    def show_message(self, message, message_type="error"):
        """Show a message banner at the top of the modal."""
        if message_type == "success":
            self.message_banner.configure(fg_color="#C8E6C9", text_color="black")  # Green for success
        else:
            self.message_banner.configure(fg_color="#FFCDD2", text_color="black")  # Red for error

        self.message_banner.configure(text=message)
        self.message_banner.pack(fill="x", padx=10, pady=5)

        # Hide after 3 seconds
        self.after(3000, self.message_banner.pack_forget)

    def add_footer_button(self, text, command, **kwargs):
        """Add a button to the footer frame."""
        button = ctk.CTkButton(self.footer_frame, text=text, command=command, **kwargs)
        button.pack(side="right", padx=5)