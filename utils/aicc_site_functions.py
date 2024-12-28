from pathlib import Path
import requests
from urllib.parse import quote
import platform
import locale

class AICCImporter:
    BASE_URL = "https://aicharactercards.com/wp-json/pngapi/v1/image"

    @staticmethod
    def fetch_card(card_id, target_file_path):
        """Fetch a card PNG file from the API based on the given card ID and save it to the specified file path."""
        try:
            # Validate and parse the card ID
            parts = card_id.split("/")
            if len(parts) != 3 or parts[0] != "AICC":
                raise ValueError("Invalid card ID format. Expected 'AICC/author/title'.")

            # Encode URL components
            author = quote(parts[1])
            title = quote(parts[2])
            url = f"{AICCImporter.BASE_URL}/{author}/{title}"

            # Generate the referer for logging purposes
            referer = (
                f"OS: {platform.system()} {platform.release()} ({platform.architecture()[0]}), "
                f"Processor: {platform.processor()}, Locale: {locale.getdefaultlocale()[0]}"
            )

            headers = {
                "User-Agent": "AICardVault/1.0",
                "Referer": referer,
            }

            # Send GET request to the API
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code != 200:
                print(f"Response: {response.text[:500]}")  # Debugging: Log response
                raise ValueError(f"API returned an error: {response.status_code} - {response.reason}")

            # Validate response Content-Type
            content_type = response.headers.get("Content-Type")
            if content_type != "image/png":
                print(f"Response content:\n{response.text[:500]}")  # Debugging: Log response
                raise ValueError(f"Unexpected Content-Type: {content_type}")

            # Save the PNG file directly to the target file path
            with target_file_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Validate the file's integrity using PNG magic bytes
            with target_file_path.open("rb") as f:
                header = f.read(8)
                if not header.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Downloaded file is not a valid PNG.")

            print(f"Downloaded {target_file_path.name} successfully to {target_file_path.parent}.")

            # Return the file path
            return str(target_file_path)

        except requests.exceptions.RequestException as e:
            print(f"HTTP Error: {e}")
            raise
        except Exception as e:
            print(f"Error fetching card: {e}")
            raise
