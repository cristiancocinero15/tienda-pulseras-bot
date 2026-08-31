# Tienda de Pulseras - Bot de Telegram

Bot con sistema de usuarios (crear cuenta / iniciar sesión / cerrar sesión), catálogo gestionable por el admin (fotos recortadas a 1:1), lista de usuarios para el admin, carrito de compra, validación de zona de entrega (solo Vinaròs, hasta 1 km) y pago online.

## 1. Instalar dependencias

```bash
pip install python-telegram-bot pillow --break-system-packages
```

## 2. Crear el bot en Telegram

1. Habla con **@BotFather** en Telegram.
2. `/newbot` y sigue los pasos → te da un **token**.
3. Para pagos: `/mybots` → tu bot → **Payments** → conecta una pasarela (ej. Stripe) → te da un **provider_token**.

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

Al arrancar por primera vez se crea `tienda.db` y se cargan las 10 pulseras de ejemplo de `/imagenes`.

## Cómo funciona

### `/start`
- Sesión activa → entra directo al menú.
- Sin sesión → "🆕 Crear cuenta" o "🔑 Iniciar sesión".

### Crear cuenta
1. Nombre de usuario (si es `ADMIN_USERNAME` → pide contraseña; si ya está cogido → sugiere una variante).
2. Escribes tu teléfono a mano, con prefijo de país (ej. `+34612345678`).
3. Confirmas con un único botón "✅ Crear" → se borra ese mensaje de confirmación y aparece el menú.

### Iniciar sesión (mover la cuenta a otro móvil/chat)
1. Nombre de usuario.
2. Admin → contraseña. Usuario normal → escribe el teléfono; si coincide con el guardado, la cuenta se traslada a este chat.

### 🚪 Cerrar sesión
Disponible para cliente y admin en el menú. Al cerrar sesión, hace falta volver a iniciar sesión (usuario + teléfono, o usuario + contraseña si eres el admin) para volver a usar el bot desde ese chat.

### Catálogo y carrito
- 🎨 Ver catálogo, 🛒 Carrito con botón "⬅️ Menú" para volver sin acumular mensajes de más.
- Los clientes **solo pueden pedir** — no pueden editar ni añadir productos, y si mandan una foto o archivo el bot les avisa de que solo se atiende por chat de texto/botones.

### Panel de admin
- **➕ Añadir producto**: nombre → precio → foto (se recorta automáticamente al centro para quedar cuadrada, 1:1).
- **👥 Ver usuarios**: lista de nombres de usuario registrados (admin, activos o con sesión cerrada) — **no se muestra el número de teléfono de nadie**, ni siquiera al admin.

### Ubicación y entrega
- Comprobación silenciosa de la distancia al centro de Vinaròs (`VINAROS_LAT`/`VINAROS_LON`, radio `RADIO_MAXIMO_KM` en `bot.py`). Si está fuera, se avisa y se da el contacto.

### Contacto
- 📞 Contacto: +34 614378910 · 👤 Admin: @cristiancocinero15

### ⚠️ Sobre "no se puede borrar el chat"
No es algo que un bot pueda controlar: borrar o vaciar el chat es una acción del propio cliente de Telegram de cada persona (cliente o admin), no del bot. No existe ninguna API de Telegram que permita a un bot bloquear eso para unos usuarios sí y para otros no.

## Desplegar en Railway (24/7 sin PC)

1. Sube `bot.py`, `db.py`, `Procfile`, `requirements.txt`, `generar_imagenes.py` y la carpeta `imagenes` a tu repo de GitHub.
2. Railway → "Deploy from GitHub repo".
3. Variables: `BOT_TOKEN`, `PROVIDER_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.

⚠️ El sistema de archivos de Railway no es persistente entre redeploys: `tienda.db` y las fotos que suba el admin se perderán si vuelves a desplegar, salvo que añadas un **Volume** (Settings → Volumes) — pregúntame si quieres que te ayude a configurarlo.

## Personalizar

- **Radio de entrega**: `RADIO_MAXIMO_KM` en `bot.py`.
- **Coordenadas de Vinaròs**: `VINAROS_LAT` / `VINAROS_LON`.
- **Teléfono de contacto**: `CONTACTO_TELEFONO`.
- **Pulseras de ejemplo iniciales**: `generar_imagenes.py` + `SEED_PRODUCTOS` en `bot.py`.
