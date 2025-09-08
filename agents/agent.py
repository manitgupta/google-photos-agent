import os
import time
import google.auth
from google.cloud import storage
from google import genai
from google.genai.types import GenerateContentConfig, Modality
from io import BytesIO
from PIL import Image

def generate_collage_from_local_photos(local_photo_paths: list[str], prompt: str):
    """
    Orchestrates the process of uploading local photos to GCS and generating a collage.

    Args:
        local_photo_paths: A list of paths to local image files.
        prompt: The text prompt for the collage generation.
    """
    credentials, project_id = None, None
    try:
        credentials, project_id = google.auth.default()
        if not project_id:
            raise EnvironmentError("Google Cloud project ID not found. Please configure your environment.")
        
        print(f"Discovered Google Cloud Project ID: {project_id}")

    except google.auth.exceptions.DefaultCredentialsError:
        print("Authentication failed. Please run 'gcloud auth application-default login' in your terminal.")
        return

    bucket_name = f"photos-{project_id}"
    output_folder = "generated-collages"
    upload_folder = "uploads"

    print(f"Using GCS Bucket: {bucket_name}")

    # 1. Upload local photos to GCS
    storage_client = storage.Client(credentials=credentials)
    bucket = storage_client.bucket(bucket_name)

    # 2. Generate the collage using the GenAI API
    print("\nStep 2: Calling the image generation API...")
    
    # Create Image objects for the API
    images = [Image.open(path) for path in local_photo_paths]

    output_gcs_uri = f"gs://{bucket_name}/{output_folder}/"

    client = genai.Client(vertexai=True, project=project_id, location="global")
    response = client.models.generate_content(
        model="gemini-2.5-flash-image-preview",
        contents=images + [prompt],
        config=GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE]),
    )

    
    for part in response.candidates[0].content.parts:
        if part.text:
            print(part.text)
        elif part.inline_data:
            image = Image.open(BytesIO((part.inline_data.data)))
            image.save("collage.png")


if __name__ == "__main__":
    # --- Example Usage ---
    
    # This script is in 'agents/', and the photos are in 'google-photos/static/'
    # So we need to use relative paths to go up one level and then down.
    photo_directory = os.path.join(os.path.dirname(__file__), '..', 'google-photos', 'static')
    
    # List of photos to include in the collage
    photos_to_use = [
        "city_park.jpeg",
        "college.jpeg",
        "goa.jpeg",
        "home.jpeg",
    ]
    
    local_paths = [os.path.join(photo_directory, name) for name in photos_to_use]

    # The prompt to guide the collage generation
    collage_prompt = "A collage of these photos without editing them, just combine the photos into a collage"

    print("--- Starting Memory Agent ---")
    generate_collage_from_local_photos(
        local_photo_paths=local_paths,
        prompt=collage_prompt
    )
    print("--- Memory Agent Finished ---")