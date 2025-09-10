import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.environ.get("GOOGLE_PHOTOS_BASE_URL")

def create_post(user_id: str, memory_title: str, memory_description: str, memory_media: str, base_url: str = BASE_URL):
    """
    Sends a POST request to the /api/memories endpoint to create a new memory.

    Args:
        user_id (str): The ID of the user creating the memory.
        memory_title (str): The title of the memory.
        memory_description (str): The description of the memory.
        memory_media (str): A GCS URL for media associated with the memory. 
        base_url (str, optional): The base URL of the API. Defaults to BASE_URL.

    Returns:
        dict: The JSON response from the API if the request is successful.
              Returns None if an error occurs.

    Raises:
        requests.exceptions.RequestException: If there's an issue with the network request (e.g., connection error, timeout).
    """
    url = f"{base_url}/api/memories"
    headers = {"Content-Type": "application/json"}
    payload = {
        "user_id": user_id,
        "memory_title": memory_title,
        "memory_description": memory_description,
        'memory_media': memory_media
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        print(f"Successfully created memory. Status Code: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating memory: {e}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from {url}. Response text: {response.text}")
        return None