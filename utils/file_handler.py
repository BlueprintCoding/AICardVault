import os
import shutil

class FileHandler:
    def __init__(self):
        self.base_path = os.path.join(os.getcwd(), "CharacterCards")

        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def handle_upload(self, file_path):
        file_name = os.path.basename(file_path)
        character_name = os.path.splitext(file_name)[0]
        character_dir = os.path.join(self.base_path, character_name)

        if not os.path.exists(character_dir):
            os.makedirs(character_dir)

        # Copy file to character directory
        shutil.copy(file_path, character_dir)
        return f"Uploaded {file_name} to {character_dir}"
