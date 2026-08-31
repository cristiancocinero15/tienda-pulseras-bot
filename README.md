# Tienda de Pulseras - Bot de Telegram

Bot con sistema de usuarios (crear cuenta / iniciar sesión, verificación por número de Telegram), catálogo de pulseras gestionable por el admin, carrito de compra, validación de zona de entrega (solo Vinaròs, hasta 1 km) y pago online.

## 1. Instalar dependencias

```bash
pip install python-telegram-bot --break-system-packages
```

## 2. Crear el bot en Telegram

1. Habla con **@BotFather** en Telegram.
2. `/newbot` y sigue los pasos → te da un **token**.
3. Para pagos: en @BotFather usa `/mybots` → tu bot → **Payments** → conecta una pasarela (ej. Stripe) → te da un **provider_token**.

## 3. Configurar variables de entorno

```bash
export BOT_TOKEN="tu_token_de_botfather"
export PROVIDER_TOKEN="tu_provider_token_de_pagos"
export ADMIN_USERNAME="cristiancocinero15"
export ADMIN_PASSWORD="la_contraseña_que_tú_elijas"
```

🔒 **Nunca subas `ADMIN_PASSWORD` al código ni a GitHub.** Solo se pone como variable de entorno (en Railway: pestaña "Variables").

## 4. Ejecutar el bot

```bash
python3 bot.py
```

Al arrancar por primera vez se crea la base de datos `tienda.db` (usuarios y productos) y se cargan las 10 pulseras de ejemplo ya generadas en `/imagenes`.

## Cómo funciona

### `/start`
- Si el chat ya tiene una cuenta asociada, entra directo al menú.
- Si no, se ofrece **"🆕 Crear cuenta"** o **"🔑 Iniciar sesión"**.

### Crear cuenta
1. Pide un nombre de usuario.
   - Si es `ADMIN_USERNAME` → pide la contraseña (`ADMIN_PASSWORD`).
   - Si ya está cogido → sugiere una variante (ej. `nombre1`); si la rechazas, se te indica que contactes con el admin.
2. Para usuarios normales, pide compartir el número de teléfono con un botón (verificado por Telegram, gratis — no se envía ningún SMS).
3. Cuenta creada, listo para usar el bot.

### Iniciar sesión (mover la cuenta a otro móvil/chat)
1. Pide el nombre de usuario.
2. Si es el admin → pide la contraseña.
3. Si es un usuario normal → pide compartir el número de teléfono; si coincide con el que quedó guardado al crear la cuenta, la sesión se traslada a este chat.

### Catálogo y carrito
- 🎨 Ver catálogo: envía cada producto como foto con botón "➕ Añadir".
- 🛒 Carrito: botón disponible en todo momento, muestra lista y total.
- Los usuarios normales **solo pueden pedir**, no pueden editar ni añadir productos.

### Panel de admin
- Solo aparece el botón "➕ Añadir producto (admin)" si has entrado como `ADMIN_USERNAME` con la contraseña correcta.
- Flujo: nombre → precio → foto. Se guarda tal cual en el catálogo.

### Ubicación y entrega
- Al finalizar pedido, el bot pide la ubicación del usuario.
- Se comprueba en silencio la distancia al centro de Vinaròs (`VINAROS_LAT`/`VINAROS_LON` en `bot.py`). Si está a más de 1 km (`RADIO_MAXIMO_KM`), se informa de que no se puede entregar ahí y se da el contacto.
- Si está dentro del radio, se envía la factura de pago (Telegram Payments).

### Contacto
- Botón "📞 Contacto" en el menú: muestra el teléfono (614378910) y el usuario del admin.

## Desplegar en la nube desde el móvil (Railway, 24/7 sin PC)

1. Sube todos estos archivos (`bot.py`, `db.py`, `Procfile`, `requirements.txt`, `generar_imagenes.py` y la carpeta `imagenes`) a tu repositorio de **GitHub**.
2. Ve a **railway.app** → "Login with GitHub" → "New Project" → "Deploy from GitHub repo".
3. En **Variables**, añade: `BOT_TOKEN`, `PROVIDER_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
4. Railway instalará `requirements.txt` y arrancará el bot con el `Procfile`.

⚠️ Railway borra los archivos del contenedor en cada redeploy (el sistema de ficheros no es persistente por defecto). Eso significa que **la base de datos `tienda.db` y las fotos nuevas que suba el admin se perderán** si vuelves a desplegar. Para que sobrevivan a los redeploys, en Railway puedes añadir un **Volume** (Settings → Volumes) — pregúntame si quieres que te ayude a configurarlo.

## Personalizar

- **Radio de entrega**: `RADIO_MAXIMO_KM` en `bot.py`.
- **Coordenadas del centro de Vinaròs**: `VINAROS_LAT` / `VINAROS_LON` en `bot.py`.
- **Teléfono de contacto**: `CONTACTO_TELEFONO` en `bot.py`.
- **Pulseras de ejemplo iniciales**: `generar_imagenes.py` + lista `SEED_PRODUCTOS` en `bot.py`.
