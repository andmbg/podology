import re
import hashlib
import base64


def episode_hash(input_string, length=5):
    """
    Return a custom 5-character hash of a string using SHA-256 and base64 encoding.
    Only returns a-z, A-Z, and 0-9 characters, allowing for 916,132,832 hashes.
    """
    # Create a sha256 hash object
    hash_object = hashlib.sha256(input_string)
    # Get the hexadecimal digest
    hex_digest = hash_object.digest()
    # Encode the digest using base64 with a custom character set
    base64_hash = base64.urlsafe_b64encode(hex_digest).decode("utf-8")
    # Remove non-alphanumeric characters
    alphanumeric_hash = re.sub(r"[^a-zA-Z0-9]", "", base64_hash)

    # Truncate the hash to the desired length
    custom_hash = alphanumeric_hash[:length]

    return custom_hash
