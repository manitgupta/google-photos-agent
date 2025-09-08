from google.adk.agents import Agent
from google.adk.tools import tool
from PIL import Image
import math

@tool
def create_collage(image_paths: list[str], output_path: str):
    """
    Generates a collage from a list of image paths.

    Args:
        image_paths: A list of paths to the images.
        output_path: The path to save the collage to.
    """
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
        collage.save(output_path)
    return f"Collage saved to {output_path}"

root_agent = Agent(
    model='gemini-2.5-flash-image-preview',
    name='root_agent',
    description='A helpful assistant for creating image collages.',
    instruction='If the user provides a list of image, create a collage of those images.',
    tools=[create_collage]
)
