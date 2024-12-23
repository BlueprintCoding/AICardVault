import json
import os

class SillyTavernTagManager:
    def __init__(self, sillytavern_path):
        self.sillytavern_path = sillytavern_path
        self.settings_file = os.path.join(sillytavern_path, "settings.json")
        self.tags = []       # List of tags
        self.tag_map = {}    # Mapping of characters to tag IDs
        self.load_tags()

    def load_tags(self):
        """Load tags from SillyTavern settings.json."""
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as file:
                self.settings = json.load(file)
            self.tags = self.settings.get("tags", [])
            self.tag_map = self.settings.get("tag_map", {})
        else:
            self.settings = {}
            self.tags = []
            self.tag_map = {}

    def reload_tags(self):
        """Reload tags and mappings."""
        print("Reloading tags...")
        self.load_tags()

    def save_tags(self):
        print("Saving tags...")  # Debug
        self.settings["tags"] = self.tags
        self.settings["tag_map"] = self.tag_map
        with open(self.settings_file, "w") as file:
            json.dump(self.settings, file, indent=4)
        # print(f"Tags saved: {self.tags}")  # Debug
        # print(f"Tag map saved: {self.tag_map}")  # Debug


    def add_tag(self, tag_name):
        """Add a new tag globally."""
        if not any(tag["name"] == tag_name for tag in self.tags):
            new_tag = {
                "id": self.generate_unique_id(),
                "name": tag_name,
                "folder_type": "NONE",
                "filter_state": "UNDEFINED",
                "sort_order": None,
                "color": "",
                "color2": "",
                "create_date": self.get_current_timestamp()
            }
            self.tags.append(new_tag)

    def remove_tag(self, tag_name):
        """Remove a tag globally."""
        # Filter out the tag from the global tags list
        self.tags = [tag for tag in self.tags if tag["name"] != tag_name]

        # Update the tag_map for each character
        for character, tag_ids in self.tag_map.items():
            # Filter out the tag ID associated with the tag_name
            self.tag_map[character] = [
                tag_id for tag_id in tag_ids
                if not self.get_tag_by_id(tag_id) or self.get_tag_by_id(tag_id)["name"] != tag_name
            ]

        # Remove empty tag mappings
        self.tag_map = {char: ids for char, ids in self.tag_map.items() if ids}

    def assign_tag(self, tag_name, character_name):
        """Assign a tag to a character."""
        tag = next((t for t in self.tags if t["name"] == tag_name), None)
        if not tag:
            self.add_tag(tag_name)
            tag = next((t for t in self.tags if t["name"] == tag_name), None)

        # Ensure character_name ends with .png
        character_name_png = f"{character_name}.png" if not character_name.endswith(".png") else character_name

        self.tag_map.setdefault(character_name_png, []).append(tag["id"])
        self.tag_map[character_name_png] = list(set(self.tag_map[character_name_png]))  # Ensure uniqueness


    def unassign_tag(self, tag_name, character_name):
        """Unassign a tag from a character."""
        tag = next((t for t in self.tags if t["name"] == tag_name), None)
        if tag:
            # Ensure character_name ends with .png
            character_name_png = f"{character_name}.png" if not character_name.endswith(".png") else character_name

            if character_name_png in self.tag_map:
                self.tag_map[character_name_png] = [
                    tag_id for tag_id in self.tag_map[character_name_png] if tag_id != tag["id"]
                ]
                if not self.tag_map[character_name_png]:
                    del self.tag_map[character_name_png]
                print(f"Tag unassigned successfully from {character_name_png}.")
            else:
                print(f"Character '{character_name}' not in tag_map.")



    def get_tag_by_id(self, tag_id):
        """Retrieve a tag by its ID."""
        return next((tag for tag in self.tags if tag["id"] == tag_id), None)

    def generate_unique_id(self):
        """Generate a unique ID for a tag."""
        import uuid
        return str(uuid.uuid4())

    def get_current_timestamp(self):
        """Get the current timestamp in milliseconds."""
        import time
        return int(time.time() * 1000)
