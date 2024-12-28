from pathlib import Path
import requests
from urllib.parse import quote
import platform
import locale

class AICCImporter:
    BASE_URL = "https://aicharactercards.com/wp-json/pngapi/v1/details"

    @staticmethod
    def fetch_card(card_id, target_file_path):
        """Fetch a card PNG file from the API and save it to the specified file path."""
        try:
            # Validate and parse the card ID
            parts = card_id.split("/")
            if len(parts) != 3 or parts[0] != "AICC":
                raise ValueError("Invalid card ID format. Expected 'AICC/author/title'.")

            # Encode URL components
            author = quote(parts[1])
            title = quote(parts[2])
            url = f"{AICCImporter.BASE_URL}/{author}/{title}"

            # Generate headers
            referer = (
                f"OS: {platform.system()} {platform.release()} ({platform.architecture()[0]}), "
                f"Processor: {platform.processor()}, Locale: {locale.getdefaultlocale()[0]}"
            )
            headers = {
                "User-Agent": "AICardVault/1.0",
                "Referer": referer,
                "Accept": "application/json",  # Explicitly request JSON
            }

            # Add an API key if required (check if your API requires it)
            # headers["Authorization"] = "Bearer <YOUR_API_KEY>"

            # Send GET request to the API for card details
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Response: {response.text[:500]}")  # Debugging: Log response
                raise ValueError(f"API returned an error: {response.status_code} - {response.reason}")

            # Parse JSON response
            card_details = response.json()

            # Download the associated PNG file
            file_url = card_details.get("file")
            if not file_url:
                raise ValueError("No file URL provided in the API response.")

            # Send GET request for the file with the same headers
            image_response = requests.get(file_url, headers=headers, stream=True)
            if image_response.status_code != 200:
                raise ValueError(f"Failed to download file: {image_response.status_code} - {image_response.reason}")

            # Save the PNG file
            with target_file_path.open("wb") as f:
                for chunk in image_response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return card_details, str(target_file_path)

        except requests.exceptions.RequestException as e:
            print(f"HTTP Error: {e}")
            raise
        except Exception as e:
            print(f"Error fetching card: {e}")
            raise
