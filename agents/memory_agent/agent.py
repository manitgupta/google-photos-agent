from google.adk.agents import Agent
from PIL import Image, ImageDraw
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
  print(f"Reading {len(gcs_paths)} images from GCS...")
  for gcs_path in gcs_paths:
    try:
      bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
      bucket = storage_client.bucket(bucket_name)
      blob = bucket.blob(blob_name)
      image_data = blob.download_as_bytes()
      image = Image.open(BytesIO(image_data))
      images.append(image)
    except Exception as e:
      print(f"Failed to load image {gcs_path}: {e}")

  print(f"Successfully loaded {len(images)} images.")
  return images

def create_collage(image_paths: list[str], output_path: str):
  """
  Generates a professional-looking collage with dynamic sizing and minimal padding.
  Handles GCS and local paths, uploads result to GCS if output_path is a GCS URI.

  Args:
      image_paths: A list of paths to the images (GCS or local).
      output_path: The path to save the collage to (GCS or local).
  """
  print("Output path:", output_path)
  if not output_path:
    output_path = "collage.jpg"
  if not os.path.splitext(output_path)[1]:
    output_path += ".jpg"

  # --- 1. Load images ---
  if not image_paths:
    return "Error: No image paths provided."

  if image_paths[0].startswith("gs://"):
    images = read_images_from_gcs(image_paths)
  else:
    images = [Image.open(p) for p in image_paths if os.path.exists(p)]

  if not images:
    return "Error: No valid images could be loaded."

  # --- 2. Collage Configuration ---
  # These parameters determine the look of your collage
  TARGET_IMAGE_WIDTH = 400  # Target width for individual images in the collage
  BORDER_SIZE = 5           # Border around each image
  SPACING = 10              # Space between images (including border)
  BACKGROUND_COLOR = (240, 240, 240) # Light gray background

  # --- 3. Pre-process images (resize and add border) ---
  processed_images = []
  for img in images:
    # Scale image down to target width, preserving aspect ratio
    w_percent = (TARGET_IMAGE_WIDTH / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(w_percent)))
    img = img.resize((TARGET_IMAGE_WIDTH, hsize), Image.Resampling.LANCZOS)

    # Add a border to each image
    bordered_img_width = img.width + 2 * BORDER_SIZE
    bordered_img_height = img.height + 2 * BORDER_SIZE
    bordered_img = Image.new('RGB', (bordered_img_width, bordered_img_height), color=(255, 255, 255)) # White border
    bordered_img.paste(img, (BORDER_SIZE, BORDER_SIZE))

    processed_images.append(bordered_img)

  # --- 4. Determine Grid Layout and Canvas Size ---
  num_images = len(processed_images)

  # Calculate columns and rows (can be optimized further for more aesthetic results)
  # For now, let's try to make it as square as possible
  cols = int(math.ceil(math.sqrt(num_images)))
  if cols == 0: cols = 1 # Avoid division by zero if no images
  rows = int(math.ceil(num_images / float(cols)))

  # Calculate total dimensions of the collage
  # Sum of individual image (with border) widths + spacing
  max_row_width = 0
  max_col_height = 0

  # Get max dimensions of processed images (they might not all be the same height after scaling to TARGET_IMAGE_WIDTH)
  current_max_img_width = max(img.width for img in processed_images)
  current_max_img_height = max(img.height for img in processed_images)

  # Total width calculation
  total_collage_width = (cols * current_max_img_width) + ((cols + 1) * SPACING)
  total_collage_height = (rows * current_max_img_height) + ((rows + 1) * SPACING)

  print(f"Creating collage canvas of {total_collage_width}x{total_collage_height} for {num_images} images in {cols}x{rows} grid.")
  collage = Image.new('RGB', (total_collage_width, total_collage_height), color=BACKGROUND_COLOR)

  # --- 5. Paste Processed Images into Collage ---
  x_offset = SPACING
  y_offset = SPACING

  for i, img_proc in enumerate(processed_images):
    row = i // cols
    col = i % cols

    # Calculate position for the current image
    # It's based on the maximum dimensions to keep cells aligned
    x_pos = SPACING + col * (current_max_img_width + SPACING)
    y_pos = SPACING + row * (current_max_img_height + SPACING)

    # Center the potentially smaller image within its allocated "slot"
    x_center_offset = (current_max_img_width - img_proc.width) // 2
    y_center_offset = (current_max_img_height - img_proc.height) // 2

    collage.paste(img_proc, (x_pos + x_center_offset, y_pos + y_center_offset))

  # --- 6. Save the final collage (to GCS or local) ---
  if output_path.startswith("gs://"):
    print(f"Saving collage to GCS: {output_path}")
    storage_client = storage.Client()
    bucket_name, blob_name = output_path.replace("gs://", "").split("/", 1)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    buffer = BytesIO()
    collage.save(buffer, format='JPEG', quality=90)
    buffer.seek(0)
    blob.upload_from_file(buffer)
    final_path_msg = output_path
  else:
    print(f"Saving collage locally: {output_path}")
    collage.save(output_path, quality=90)
    final_path_msg = output_path

  return f"Collage successfully saved to {final_path_msg}"


# --- Agent Definition (unchanged) ---
root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A helpful assistant for creating image collages.',
    instruction='If the user provides a list of gcs image paths, create a collage of those images.',
    tools=[create_collage],
)