import requests
from urllib.parse import quote
import platform
import os
import locale

class AICCImporter:
    BASE_URL = "https://aicharactercards.com/wp-json/pngapi/v1/image"

    @staticmethod
    def fetch_card(card_id):
        """Fetch a card PNG file from the API based on the given card ID."""
        try:
            parts = card_id.split("/")
            if len(parts) != 3 or parts[0] != "AICC":
                raise ValueError("Invalid card ID format. Expected 'AICC/author/title'.")

            author = quote(parts[1])  # Ensure URL-encoded
            title = quote(parts[2])   # Ensure URL-encoded
            url = f"{AICCImporter.BASE_URL}/{author}/{title}"
            referer = f"OS: {platform.system()} {platform.release()} ({platform.architecture()[0]}), Processor: {platform.processor()}, Locale: {locale.getdefaultlocale()[0]}"

            headers = {
                "User-Agent": "AICardVault/1.0",
                "Referer": referer,
            }

            # Perform the GET request
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code != 200:
                print(f"Response: {response.text[:500]}")  # Log response for debugging
                raise ValueError(f"API returned an error: {response.status_code} - {response.reason}")

            # Debugging: Ensure Content-Type is PNG
            content_type = response.headers.get("Content-Type")
            if content_type != "image/png":
                print(f"Response content:\n{response.text[:500]}")  # Log partial response
                raise ValueError(f"Unexpected Content-Type: {content_type}")

            # Save the PNG content locally
            filename = f"{title}.png"
            filepath = os.path.join(os.getcwd(), filename)

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Ensure file integrity by checking magic bytes
            with open(filepath, "rb") as f:
                header = f.read(8)
                if not header.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Downloaded file is not a valid PNG.")

            print(f"Downloaded {filename} successfully.")
            return filepath

        except requests.exceptions.HTTPError as e:
            print(f"HTTP Error: {e}")
            print(f"Response text: {e.response.text}")
            raise
        except Exception as e:
            print(f"Error fetching card: {e}")
            raise
