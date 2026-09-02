# Tienda de Pulseras - Bot de Telegram

Bot con sistema de usuarios (crear cuenta / iniciar sesión / cerrar sesión, verificación por **email** con código de 6 dígitos), catálogo por categorías gestionable por el admin (fotos recortadas a 1:1), lista de usuarios para el admin, carrito de compra, validación de zona de entrega (solo Vinaròs, hasta 1 km) y pago online.

## 1. Instalar dependencias

```bash
pip install python-telegram-bot pillow --break-system-packages
```

(El envío de emails usa `smtplib`, que ya viene incluido en Python — no hace falta instalar nada más.)

## 2. Crear el bot en Telegram

1. Habla con **@BotFather** → `/newbot` → sigue los pasos → te da un **token**.
2. Para pagos: `/mybots` → tu bot → **Payments** → conecta tu pasarela (Stripe, Smart Glocal...) → te da un **provider_token**.

## 3. Crear la "contraseña de aplicación" de Gmail (para enviar los códigos)

1. Ve a tu **Cuenta de Google** → **Seguridad**.
2. Activa la **Verificación en dos pasos** si no la tienes activada (es obligatorio para poder crear contraseñas de aplicación).
3. Busca **"Contraseñas de aplicaciones"** → créala (puedes llamarla "Tienda Pulseras Bot") → Google te da una contraseña de 16 caracteres.
4. Esa contraseña (no la de tu Gmail normal) es la que usarás como `GMAIL_APP_PASSWORD`.

## 4. Configurar variables de entorno

```bash
export BOT_TOKEN="token_del_bot"
export PROVIDER_TOKEN="tu_provider_token_de_pagos"
export ADMIN_USERNAME="cristiancocinero15"
export ADMIN_PASSWORD="la_contraseña_que_tú_elijas"
export GMAIL_ADDRESS="tu_correo@gmail.com"
export GMAIL_APP_PASSWORD="la_contraseña_de_aplicación_de_16_caracteres"
```

🔒 **Nunca subas `ADMIN_PASSWORD` ni `GMAIL_APP_PASSWORD` al código ni a GitHub.** Solo se ponen como variables de entorno (en Railway: pestaña "Variables").

⚠️ Si no configuras Gmail, el bot sigue funcionando: como respaldo, te muestra el código directamente en el chat de Telegram en vez de mandarlo por email (útil para probar sin tener el email configurado todavía).

## 5. Ejecutar el bot

```bash
python3 bot.py
```

Al arrancar por primera vez se crea `tienda.db` y se cargan las 10 pulseras de ejemplo de `/imagenes`.

## Cómo funciona

### `/start`
- Se borra el mensaje anterior del bot y el propio `/start`, para mantener el chat limpio.
- Sesión activa → entra directo al menú.
- Sin sesión → "🆕 Crear cuenta" o "🔑 Iniciar sesión".

### Crear cuenta / Iniciar sesión
1. Nombre de usuario (si es `ADMIN_USERNAME` → pide contraseña; si ya está cogido → sugiere una variante).
2. Escribes tu **email**.
3. El bot te manda un correo con un **código de 6 dígitos** y un botón "Confirmar directamente".
4. Puedes verificar de dos formas:
   - Escribiendo el código de 6 dígitos en el chat de Telegram.
   - Pulsando el botón "Confirmar" del email — te lleva directo a Telegram y completa la verificación en un toque, sin escribir nada.
5. Si el código es incorrecto, se invalida solo y se genera + reenvía uno nuevo automáticamente.

### 🚪 Cerrar sesión
Disponible para cliente y admin en el menú.

### Catálogo por categorías
- 🎨 Ver catálogo → si hay más de una categoría, primero eliges cuál ver (o "🗂️ Ver todo").
- Botones "🛒 Ver carrito" y "⬅️ Menú" para no acumular mensajes.
- Los clientes solo pueden pedir — no editan ni añaden productos, y si mandan fotos/archivos el bot avisa que solo se atiende por chat de texto/botones.

### Panel de admin
- **➕ Añadir producto**: nombre → elegir categoría existente o crear una nueva → precio → foto (recortada automáticamente a 1:1).
- **👥 Ver usuarios**: lista de nombres de usuario — nunca el email, ni siquiera para el admin.

### Ubicación y entrega
- Comprobación silenciosa de la distancia al centro de Vinaròs (`VINAROS_LAT`/`VINAROS_LON`, radio `RADIO_MAXIMO_KM` en `bot.py`).

### Contacto
- 📞 +34 614378910 · 👤 Admin: @cristiancocinero15

## Desplegar en Railway (24/7 sin PC)

1. Sube `bot.py`, `db.py`, `Procfile`, `requirements.txt`, `generar_imagenes.py` y la carpeta `imagenes` a tu repo de GitHub.
2. Railway → "Deploy from GitHub repo".
3. Variables: `BOT_TOKEN`, `PROVIDER_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`.
4. Un solo servicio, un solo bot — ya no hace falta ningún bot segundo ni servicio extra.

⚠️ El sistema de archivos de Railway no es persistente entre redeploys: `tienda.db` (usuarios, emails, productos) y las fotos que suba el admin se perderán si vuelves a desplegar, salvo que añadas un **Volume**:

1. Ve a la **vista principal del proyecto** en Railway (el lienzo con las cajas, no la pestaña Settings).
2. Clic derecho en un hueco vacío del lienzo (o `Cmd+K` / `Ctrl+K`) → **"Create Volume"**.
3. Conéctalo a tu servicio `tienda-pulseras-bot`.
4. **Mount path**: `/app/data`
5. Guarda y espera al redeploy.

No hace falta ninguna variable extra — el bot detecta el Volume automáticamente (usa la variable `RAILWAY_VOLUME_MOUNT_PATH` que Railway inyecta sola). A partir de ahí, usuarios, emails y fotos sobreviven a los redeploys.

## Personalizar

- **Radio de entrega**: `RADIO_MAXIMO_KM` en `bot.py`.
- **Coordenadas de Vinaròs**: `VINAROS_LAT` / `VINAROS_LON`.
- **Teléfono de contacto**: `CONTACTO_TELEFONO`.
- **Pulseras/categorías de ejemplo iniciales**: `generar_imagenes.py` + `SEED_PRODUCTOS` en `bot.py`.
