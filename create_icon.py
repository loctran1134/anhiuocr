import os
from PIL import Image, ImageDraw

def generate_icon(output_path="app_icon.ico"):
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []

    for size in sizes:
        w, h = size
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded rectangle background (Royal blue #2563eb)
        radius = int(w * 0.22)
        margin = max(1, int(w * 0.04))
        draw.rounded_rectangle(
            [(margin, margin), (w - margin, h - margin)],
            radius=radius,
            fill=(37, 99, 235, 255)
        )

        # Draw camera / scan lens design
        cx, cy = w // 2, h // 2
        r_outer = int(w * 0.24)
        draw.ellipse(
            [(cx - r_outer, cy - r_outer), (cx + r_outer, cy + r_outer)],
            outline=(255, 255, 255, 255),
            width=max(2, int(w * 0.05))
        )
        
        # Center lens dot
        r_inner = int(w * 0.10)
        draw.ellipse(
            [(cx - r_inner, cy - r_inner), (cx + r_inner, cy + r_inner)],
            fill=(255, 255, 255, 255)
        )

        # Flash indicator
        fx = int(w * 0.70)
        fy = int(h * 0.28)
        fr = max(1, int(w * 0.04))
        draw.ellipse([(fx - fr, fy - fr), (fx + fr, fy + fr)], fill=(255, 255, 255, 220))

        images.append(img)

    images[0].save(
        output_path,
        format="ICO",
        sizes=[(s[0], s[1]) for s in sizes],
        append_images=images[1:]
    )
    print(f"Icon saved successfully at {output_path}")

if __name__ == "__main__":
    generate_icon()
