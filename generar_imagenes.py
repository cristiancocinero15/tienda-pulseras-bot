"""
Genera imágenes PNG sencillas de pulseras de goma (clásicas y combinadas)
para usar como fotos de producto en el bot de Telegram.
"""
import math
import os
from PIL import Image, ImageDraw

OUT_DIR = os.path.join(os.path.dirname(__file__), "imagenes")
os.makedirs(OUT_DIR, exist_ok=True)

SIZE = 500
CENTER = SIZE // 2
BAND_THICKNESS = 70
RADIUS = 170


def draw_bracelet(colores, filename):
    """Dibuja una pulsera circular. Si hay varios colores, se reparten
    en segmentos iguales alrededor del círculo (efecto 'combinado')."""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    bbox = [
        CENTER - RADIUS - BAND_THICKNESS // 2,
        CENTER - RADIUS - BAND_THICKNESS // 2,
        CENTER + RADIUS + BAND_THICKNESS // 2,
        CENTER + RADIUS + BAND_THICKNESS // 2,
    ]

    n = len(colores)
    step = 360 / n
    gap = 3 if n > 1 else 0  # pequeño hueco entre segmentos combinados

    for i, color in enumerate(colores):
        start = i * step + gap
        end = (i + 1) * step - gap
        draw.arc(bbox, start=start, end=end, fill=color, width=BAND_THICKNESS)
        # Redondear los extremos del segmento con círculos pequeños
        for ang in (start, end):
            rad = math.radians(ang)
            x = CENTER + RADIUS * math.cos(rad)
            y = CENTER + RADIUS * math.sin(rad)
            r = BAND_THICKNESS / 2
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

    # sombra interior suave para efecto goma
    inner_r = RADIUS - BAND_THICKNESS // 2 + 10
    draw.ellipse(
        [CENTER - inner_r, CENTER - inner_r, CENTER + inner_r, CENTER + inner_r],
        outline=(0, 0, 0, 40),
        width=3,
    )

    img.save(os.path.join(OUT_DIR, filename))
    print("Generada:", filename)


# Colores clásicos (un solo color)
CLASICOS = {
    "negro": (30, 30, 30, 255),
    "blanco": (245, 245, 245, 255),
    "rojo": (220, 40, 40, 255),
    "azul": (40, 90, 220, 255),
    "verde": (40, 160, 70, 255),
    "amarillo": (240, 200, 30, 255),
}

# Combinaciones (varios colores en la misma pulsera)
COMBINADOS = {
    "rojo_blanco": [(220, 40, 40, 255), (245, 245, 245, 255)],
    "azul_amarillo": [(40, 90, 220, 255), (240, 200, 30, 255)],
    "verde_negro": [(40, 160, 70, 255), (30, 30, 30, 255)],
    "arcoiris": [
        (220, 40, 40, 255),
        (240, 200, 30, 255),
        (40, 160, 70, 255),
        (40, 90, 220, 255),
        (150, 60, 180, 255),
    ],
}

for nombre, color in CLASICOS.items():
    draw_bracelet([color], f"clasico_{nombre}.png")

for nombre, colores in COMBINADOS.items():
    draw_bracelet(colores, f"combinado_{nombre}.png")

print("\nListo. Imágenes en:", OUT_DIR)
