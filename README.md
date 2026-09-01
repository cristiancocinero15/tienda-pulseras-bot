# Tienda de Pulseras - Bot de Telegram

Bot con sistema de usuarios (crear cuenta / iniciar sesión / cerrar sesión, verificación con un segundo bot), catálogo por categorías gestionable por el admin (fotos recortadas a 1:1), lista de usuarios para el admin, carrito de compra, validación de zona de entrega (solo Vinaròs, hasta 1 km) y pago online.

## 1. Instalar dependencias

```bash
pip install python-telegram-bot pillow --break-system-packages
```

## 2. Crear los DOS bots en Telegram

Este proyecto usa **dos bots**:
- El bot principal de la tienda (el que ya tienes).
- Un segundo bot, **solo para entregar el código de verificación** (ej. `SMSTienda_bot`). No hace nada más.

Para cada uno:
1. Habla con **@BotFather** → `/newbot` → sigue los pasos → te da un **token**.
2. Para el bot principal, además: `/mybots` → tu bot → **Payments** → conecta tu pasarela (Stripe, Smart Glocal...) → te da un **provider_token**.

⚠️ Aunque son dos bots, **ambos corren dentro del mismo programa** (`bot.py`) y comparten la misma base de datos — no hace falta ni desplegar ni programar el segundo por separado, solo darle su token.

## 3. Configurar variables de entorno

```bash
export BOT_TOKEN="token_del_bot_principal"
export PROVIDER_TOKEN="tu_provider_token_de_pagos"
export ADMIN_USERNAME="cristiancocinero15"
export ADMIN_PASSWORD="la_contraseña_que_tú_elijas"
export SMS_BOT_TOKEN="token_del_segundo_bot"
export SMS_BOT_USERNAME="SMSTienda_bot"   # el @usuario del segundo bot, sin la @
```

🔒 **Nunca subas `ADMIN_PASSWORD` al código ni a GitHub.** Solo se pone como variable de entorno (en Railway: pestaña "Variables").

## 4. Ejecutar el bot

```bash
python3 bot.py
```

Arranca los dos bots a la vez. Al arrancar por primera vez se crea `tienda.db` y se cargan las 10 pulseras de ejemplo de `/imagenes`.

## Cómo funciona

### `/start`
- Se borra el mensaje anterior del bot y el propio `/start`, para mantener el chat limpio.
- Sesión activa → entra directo al menú.
- Sin sesión → "🆕 Crear cuenta" o "🔑 Iniciar sesión".

### Crear cuenta / Iniciar sesión
1. Nombre de usuario (si es `ADMIN_USERNAME` → pide contraseña; si ya está cogido → sugiere una variante).
2. Escribes tu teléfono a mano, con prefijo de país (ej. `+34612345678`).
3. El bot te da un botón para hablar con el segundo bot (`@SMSTienda_bot`). Le das a *Iniciar* ahí y te manda un **código de 6 caracteres (3 letras mayúsculas + 3 números, aleatorio)**.
4. Vuelves al chat de la tienda y escribes el código.
5. Se borra el mensaje con el botón y el que escribiste tú, y aparece el menú.

⚠️ **Importante sobre la seguridad de esto**: pasar el código por un segundo bot de Telegram no verifica de verdad que el número escrito sea real — solo confirma que tienes acceso a tu propia cuenta de Telegram, cosa que ya se sabe porque estás hablando con el bot. Para una verificación real del número físico haría falta SMS de pago (Twilio, Smart Glocal...) o usar el botón nativo de "compartir contacto" de Telegram.

### 🚪 Cerrar sesión
Disponible para cliente y admin en el menú.

### Catálogo por categorías
- 🎨 Ver catálogo → si hay más de una categoría, primero eliges cuál ver (o "🗂️ Ver todo").
- Cada foto muestra su categoría y precio.
- Botones "🛒 Ver carrito" y "⬅️ Menú" al final para no acumular mensajes.
- Los clientes solo pueden pedir — no editan ni añaden productos, y si mandan fotos/archivos el bot avisa que solo se atiende por chat de texto/botones.

### Panel de admin
- **➕ Añadir producto**: nombre → elegir categoría existente o crear una nueva → precio → foto (recortada automáticamente a 1:1).
- **👥 Ver usuarios**: lista de nombres de usuario — nunca el teléfono, ni siquiera para el admin.

### Ubicación y entrega
- Comprobación silenciosa de la distancia al centro de Vinaròs (`VINAROS_LAT`/`VINAROS_LON`, radio `RADIO_MAXIMO_KM` en `bot.py`).

### Contacto
- 📞 +34 614378910 · 👤 Admin: @cristiancocinero15

## Desplegar en Railway (24/7 sin PC)

1. Sube `bot.py`, `db.py`, `Procfile`, `requirements.txt`, `generar_imagenes.py` y la carpeta `imagenes` a tu repo de GitHub.
2. Railway → "Deploy from GitHub repo".
3. Variables: `BOT_TOKEN`, `PROVIDER_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SMS_BOT_TOKEN`, `SMS_BOT_USERNAME`.
4. Un solo servicio arranca los dos bots a la vez (no hace falta crear un segundo servicio en Railway).

⚠️ El sistema de archivos de Railway no es persistente entre redeploys: `tienda.db` y las fotos que suba el admin se perderán si vuelves a desplegar, salvo que añadas un **Volume** (Settings → Volumes).

## Personalizar

- **Radio de entrega**: `RADIO_MAXIMO_KM` en `bot.py`.
- **Coordenadas de Vinaròs**: `VINAROS_LAT` / `VINAROS_LON`.
- **Teléfono de contacto**: `CONTACTO_TELEFONO`.
- **Pulseras/categorías de ejemplo iniciales**: `generar_imagenes.py` + `SEED_PRODUCTOS` en `bot.py`.
