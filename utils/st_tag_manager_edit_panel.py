import json
import os
import unicodedata
from pathlib import Path

class SillyTavernTagManager:
    def __init__(self, sillytavern_path):
        self.sillytavern_path = sillytavern_path
        self.settings_file = Path(sillytavern_path).resolve() / "settings.json"
        self.tags = []       # List of tags
        self.tag_map = {}    # Mapping of characters to tag IDs
        self.load_tags()

    def normalize_filename(self, filename):
        """Normalize filenames to handle special characters consistently."""
        return unicodedata.normalize("NFC", filename)

    def load_tags(self):
        """Load tags from SillyTavern settings.json."""
        if self.settings_file.exists():
            try:
                with self.settings_file.open("r", encoding="utf-8", errors="replace") as file:
                    self.settings = json.load(file)

                # Normalize keys in the tag map
                self.tag_map = {
                    self.normalize_filename(key): value
                    for key, value in self.settings.get("tag_map", {}).items()
                }
                self.tags = self.settings.get("tags", [])
                # Debug logging
                # print("Tag map loaded with normalized keys:", list(self.tag_map.keys()))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                print(f"Error reading or decoding settings.json: {e}")
                self.settings = {}
                self.tags = []
                self.tag_map = {}
        else:
            print(f"Settings file not found: {self.settings_file}")
            self.settings = {}
            self.tags = []
            self.tag_map = {}


    def reload_tags(self):
        """Reload tags and mappings."""
        # print("Reloading tags...")
        self.load_tags()

    def save_tags(self):
        print("Saving tags...")  # Debug
        self.settings["tags"] = self.tags
        self.settings["tag_map"] = self.tag_map
        try:
            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump(self.settings, file, indent=4, ensure_ascii=False)  # Use `ensure_ascii=False` for proper UTF-8 handling
            print("Tags saved successfully.")
        except Exception as e:
            print(f"Error saving tags: {e}")

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

    def find_character_in_tag_map(self, character_name):
        """Find a character in the tag map, returning normalized versions if not found."""
        normalized_name = self.normalize_filename(character_name)
        if normalized_name in self.tag_map:
            return normalized_name
        print(f"Character {character_name} not found. Normalized: {normalized_name}. Available keys: {list(self.tag_map.keys())}")
        return None

    def assign_tag(self, tag_name, character_name):
        """Assign a tag to a character."""
        tag = next((t for t in self.tags if t["name"] == tag_name), None)
        if not tag:
            self.add_tag(tag_name)
            tag = next((t for t in self.tags if t["name"] == tag_name), None)

        # Ensure character_name ends with .png
        character_name_png = f"{character_name}.png" if not character_name.endswith(".png") else character_name

        # Normalize character name before assigning
        normalized_character_name = self.normalize_filename(character_name_png)
        self.tag_map.setdefault(normalized_character_name, []).append(tag["id"])
        self.tag_map[normalized_character_name] = list(set(self.tag_map[normalized_character_name]))  # Ensure uniqueness

    def unassign_tag(self, tag_name, character_name):
        """Unassign a tag from a character."""
        tag = next((t for t in self.tags if t["name"] == tag_name), None)
        if tag:
            # Ensure character_name ends with .png
            character_name_png = f"{character_name}.png" if not character_name.endswith(".png") else character_name

            # Normalize character name before unassigning
            normalized_character_name = self.normalize_filename(character_name_png)

            if normalized_character_name in self.tag_map:
                self.tag_map[normalized_character_name] = [
                    tag_id for tag_id in self.tag_map[normalized_character_name] if tag_id != tag["id"]
                ]
                if not self.tag_map[normalized_character_name]:
                    del self.tag_map[normalized_character_name]
                print(f"Tag unassigned successfully from {normalized_character_name}.")
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
