import base64
import json
import struct

class PNGMetadataReader:
    PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

    @staticmethod
    def _calculate_crc32(data):
        crc = 0xffffffff
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
        return crc ^ 0xffffffff

    @staticmethod
    def _read_chunks(data):
        if not data.startswith(PNGMetadataReader.PNG_SIGNATURE):
            raise ValueError("Invalid PNG header")

        chunks = []
        idx = len(PNGMetadataReader.PNG_SIGNATURE)

        while idx < len(data):
            length = struct.unpack(">I", data[idx:idx + 4])[0]
            idx += 4

            chunk_type = data[idx:idx + 4].decode("ascii")
            idx += 4

            chunk_data = data[idx:idx + length]
            idx += length

            crc = struct.unpack(">I", data[idx:idx + 4])[0]
            idx += 4

            calculated_crc = PNGMetadataReader._calculate_crc32(
                chunk_type.encode("ascii") + chunk_data
            )
            if crc != calculated_crc:
                raise ValueError(f"CRC mismatch for chunk type {chunk_type}")

            chunks.append({"type": chunk_type, "data": chunk_data, "crc": crc})

        return chunks

    @staticmethod
    def extract_text_metadata(file_path):
        with open(file_path, "rb") as f:
            data = f.read()

        chunks = PNGMetadataReader._read_chunks(data)

        for chunk in chunks:
            if chunk["type"] == "tEXt":
                # tEXt chunk contains null-separated keyword and text
                text_data = chunk["data"]
                _, value = text_data.split(b'\x00', 1)
                value = value.decode("ascii")

                # Decode Base64 if applicable
                try:
                    decoded_json = base64.b64decode(value).decode("utf-8")
                    return json.loads(decoded_json)
                except base64.binascii.Error:
                    raise ValueError("Failed to decode Base64 metadata")

        raise ValueError("No tEXt metadata found")

    @staticmethod
    def get_highest_spec_fields(metadata):
        """
        Extract and return all fields for the highest spec version available.
        """
        if not isinstance(metadata, dict):
            raise ValueError("Invalid metadata format. Expected a dictionary.")

        # Default to spec version 1
        highest_spec_data = metadata.copy()

        # Check if spec_version is present and prioritize the highest one
        if "spec_version" in metadata:
            spec_version = metadata.get("spec_version")
            if spec_version in ["2.0", "3.0"]:  # Add more spec versions if applicable
                highest_spec_data = metadata.get("data", {}).copy()
            else:
                highest_spec_data = metadata.copy()

        # Return the fields for the highest spec
        return highest_spec_data

    @staticmethod
    def extract_highest_spec_fields(file_path):
        """
        Extracts the metadata from a PNG file and returns fields for the highest spec version.
        """
        metadata = PNGMetadataReader.extract_text_metadata(file_path)
        return PNGMetadataReader.get_highest_spec_fields(metadata)


# Usage example
# Assuming the PNG file contains the Base64-encoded JSON metadata:
# png_reader = PNGMetadataReader()
# highest_spec_fields = png_reader.extract_highest_spec_fields("path_to_your_file.png")
# print(highest_spec_fields)
