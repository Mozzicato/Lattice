"""
Generate a synthetic 'handwritten' note for testing.
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_sample_image():
    # Create white canvas
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), color='white')
    d = ImageDraw.Draw(img)
    
    # Try to load a font, or use default
    try:
        # Windows path for Segoe UI or similar
        font = ImageFont.truetype("arial.ttf", 24)
        title_font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()
        title_font = font

    # Draw content
    d.text((50, 50), "Calculus I - Limits", fill='black', font=title_font)
    
    content = [
        "Date: Feb 5, 2026",
        "",
        "The concept of a limit is fundamental to calculus.",
        "We say that:",
        "",
        "    lim (x -> a) f(x) = L",
        "",
        "If f(x) gets closer to L as x gets closer to a.",
        "",
        "Example:",
        "Let f(x) = x^2. As x -> 2, f(x) -> 4.",
        "",
        "$$ \int x^2 dx = x^3/3 + C $$",
        "",
        "Graph:",
        "(Imagine a parabola here)"
    ]
    
    y = 120
    for line in content:
        d.text((50, y), line, fill='black', font=font)
        y += 40
        
    # Draw a simple parabola
    points = []
    for x in range(200, 600):
        # x goes 200->600. Center 400.
        # norm_x goes -2 to 2
        norm_x = (x - 400) / 50.0  
        norm_y = norm_x ** 2
        # y scale
        plot_y = 800 - (norm_y * 50)
        points.append((x, plot_y))
    
    d.line(points, fill='blue', width=2)
    
    filename = "sample_note.png"
    img.save(filename)
    print(f"Created {filename}")
    return filename

if __name__ == "__main__":
    create_sample_image()
