from pathlib import Path
import shutil

class FileHandler:
    def __init__(self):
        self.base_path = Path.cwd() / "CharacterCards"
        self.base_path.mkdir(parents=True, exist_ok=True)

    def handle_upload(self, file_path):
        file_path = Path(file_path)  # Ensure file_path is a Path object
        file_name = file_path.name
        character_name = file_path.stem
        character_dir = self.base_path / character_name

        character_dir.mkdir(parents=True, exist_ok=True)

        # Copy file to character directory
        shutil.copy(file_path, character_dir / file_name)
        return f"Uploaded {file_name} to {character_dir}"
