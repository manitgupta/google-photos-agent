from google.adk.agents import Agent
from PIL import Image
import math
from google.cloud import storage
from io import BytesIO
import os

def read_images_from_gcs(gcs_paths: list[str]) -> list[Image.Image]:
    """
    Reads images from GCS paths.

    Args:
        gcs_paths: A list of GCS paths to the images.

    Returns:
        A list of PIL Image objects.
    """
    images = []
    storage_client = storage.Client()
    for gcs_path in gcs_paths:
        bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        image_data = blob.download_as_bytes()
        image = Image.open(BytesIO(image_data))
        images.append(image)
    return images

def create_collage(image_paths: list[str], output_path: str):
    """
    Generates a collage from a list of image paths.

    Args:
        image_paths: A list of paths to the images (GCS).
        output_path: The path to save the collage to (GCS).
    """
    print("Output path:", output_path)
    if not output_path:
        output_path = "collage.jpg"
    if not os.path.splitext(output_path)[1]:
        output_path += ".jpg"

    if image_paths and image_paths[0].startswith("gs://"):
        images = read_images_from_gcs(image_paths)
    else:
        images = [Image.open(p) for p in image_paths]

    width=2000
    height=1200
    
    for img in images:
        img.thumbnail((width, height))

    cols = int(math.ceil(math.sqrt(len(images))))
    rows = int(math.ceil(len(images) / cols))
    
    if cols > 0 and rows > 0:
        collage = Image.new('RGB', (cols * width, rows * height))
        for i, img in enumerate(images):
            x = (i % cols) * width
            y = (i // cols) * height
            collage.paste(img, (x, y))
        
        if output_path.startswith("gs://"):
            storage_client = storage.Client()
            bucket_name, blob_name = output_path.replace("gs://", "").split("/", 1)
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            buffer = BytesIO()
            collage.save(buffer, format='JPEG')
            buffer.seek(0)
            blob.upload_from_file(buffer)
        else:
            collage.save(output_path)
            
    return f"Collage saved to {output_path}"

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for creating image collages.',
    instruction='If the user provides a list of gcs image paths, create a collage of those images.',
    tools=[create_collage],
)
