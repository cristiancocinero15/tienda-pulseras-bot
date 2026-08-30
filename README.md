# Tienda de Pulseras - Bot de Telegram

Bot con catálogo de pulseras de goma (colores clásicos y combinados), carrito de compra, validación de zona de entrega (solo Vinaròs, hasta 1 km) y pago online.

## 1. Instalar dependencias

```bash
pip install python-telegram-bot pillow --break-system-packages
```

## 2. Crear el bot en Telegram

1. Habla con **@BotFather** en Telegram.
2. `/newbot` y sigue los pasos → te da un **token**.
3. Para pagos: en @BotFather usa `/mybots` → tu bot → **Payments** → conecta una pasarela (ej. Stripe) → te da un **provider_token**.

## 3. Configurar variables de entorno

```bash
export BOT_TOKEN="tu_token_de_botfather"
export PROVIDER_TOKEN="tu_provider_token_de_pagos"
```

## 4. Generar las imágenes (ya incluidas en /imagenes, pero puedes regenerarlas)

```bash
python3 generar_imagenes.py
```

## 5. Ejecutar el bot

```bash
python3 bot.py
```

## Cómo funciona

- `/start` → menú con botones "🎨 Ver catálogo" y "🛒 Carrito".
- Catálogo: envía cada pulsera como foto con botón "➕ Añadir".
- Carrito: botón 🛒 en cualquier momento muestra la lista de productos añadidos y el total.
- Al pulsar "🧾 Finalizar pedido", el bot pide la ubicación del usuario.
- Solo se permite continuar si la ubicación está a **1 km o menos** del centro de Vinaròs (coordenadas configurables en `VINAROS_LAT` / `VINAROS_LON` en `bot.py`). Si no, se rechaza el pedido (no se admite Peñíscola ni otras localidades).
- Si la ubicación es válida, se envía una factura de Telegram Payments con el total del carrito.
- Al completar el pago, se confirma el pedido y se vacía el carrito.

## Desplegar en la nube desde el móvil (Railway, 24/7 sin PC)

1. Sube todos estos archivos (incluyendo `Procfile` y `requirements.txt`) a un repositorio de **GitHub** (se puede hacer desde la app o web de GitHub en el móvil).
2. Ve a **railway.app** → "Login with GitHub".
3. "New Project" → "Deploy from GitHub repo" → elige tu repositorio.
4. En **Variables**, añade:
   - `BOT_TOKEN`
   - `PROVIDER_TOKEN`
5. Railway instalará `requirements.txt` y arrancará el bot con el `Procfile` automáticamente. El bot quedará corriendo 24/7 sin depender de tu móvil ni PC.

## Personalizar

- **Productos y precios**: edita el diccionario `CATALOGO` en `bot.py`.
- **Colores/combinaciones de pulseras**: edita `generar_imagenes.py` (diccionarios `CLASICOS` y `COMBINADOS`).
- **Radio de entrega**: cambia `RADIO_MAXIMO_KM` en `bot.py`.
