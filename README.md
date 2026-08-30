# Tienda de Pulseras - Bot de Telegram

Bot con sistema de usuarios, catálogo de pulseras (con fotos, gestionable por el admin), carrito de compra, validación de zona de entrega (solo Vinaròs, hasta 1 km) y pago online.

## 1. Instalar dependencias

```bash
pip install python-telegram-bot pillow rembg onnxruntime --break-system-packages
```

⚠️ `rembg` (quitar el fondo de las fotos) descarga un modelo de IA de unos ~180 MB la primera vez que se usa, y necesita bastante RAM. En hostings gratuitos (como el plan Trial de Railway) puede quedarse sin memoria. Si eso pasa, el bot sigue funcionando pero guarda la foto **tal cual la mandaste**, sin quitar el fondo (se avisa en el mensaje de confirmación).

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

🔒 **Nunca subas `ADMIN_PASSWORD` al código ni a GitHub.** Solo se pone como variable de entorno (en Railway: pestaña "Variables"). Si alguien no sabe la contraseña no puede registrarse como `cristiancocinero15`, así que el nombre de usuario admin queda protegido.

## 4. Ejecutar el bot

```bash
python3 bot.py
```

Al arrancar por primera vez se crea la base de datos `tienda.db` (usuarios y productos) y se cargan las 10 pulseras de ejemplo ya generadas en `/imagenes`.

## Cómo funciona

### Registro / login (`/start`)
- Si el usuario ya está registrado, entra directo al menú.
- Si es nuevo, se le pide un nombre de usuario.
  - Si escribe el nombre del admin (`ADMIN_USERNAME`), se le pide la contraseña (`ADMIN_PASSWORD`). Si acierta, queda como admin.
  - Si el nombre ya está cogido por otra persona, se le sugiere una variante (ej. `nombre1`). Si la acepta, se registra con ese nombre; si no, se le indica que contacte con el admin para que se lo asignen.

### Catálogo y carrito
- 🎨 Ver catálogo: envía cada producto como foto con botón "➕ Añadir".
- 🛒 Carrito: botón disponible en todo momento, muestra lista y total.
- Los usuarios normales **solo pueden pedir**, no pueden editar ni añadir productos.

### Panel de admin
- Solo aparece el botón "➕ Añadir producto (admin)" si has entrado como `ADMIN_USERNAME` con la contraseña correcta.
- Flujo: nombre → precio → foto. La foto se procesa automáticamente para quitar el fondo y dejarlo en blanco, y se guarda en el catálogo.

### Ubicación y entrega
- Al finalizar pedido, el bot pide la ubicación del usuario.
- Se comprueba en silencio la distancia al centro de Vinaròs (`VINAROS_LAT`/`VINAROS_LON` en `bot.py`). Si está a más de 1 km (radio en `RADIO_MAXIMO_KM`), se informa de que no se puede entregar ahí (sin importar si es Madrid, Francia, Marruecos, etc.) y se da el contacto.
- Si está dentro del radio, se envía la factura de pago (Telegram Payments).

### Contacto
- Botón "📞 Contacto" en el menú principal: muestra el teléfono (614378910) y el usuario del admin.

## Desplegar en la nube desde el móvil (Railway, 24/7 sin PC)

1. Sube todos estos archivos (incluyendo `Procfile`, `requirements.txt`, `db.py` y la carpeta `imagenes`) a un repositorio de **GitHub**.
2. Ve a **railway.app** → "Login with GitHub" → "New Project" → "Deploy from GitHub repo".
3. En **Variables**, añade: `BOT_TOKEN`, `PROVIDER_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
4. Railway instalará `requirements.txt` y arrancará el bot con el `Procfile`.

⚠️ Railway borra los archivos del contenedor en cada redeploy (el sistema de ficheros no es persistente por defecto). Eso significa que **la base de datos `tienda.db` y las fotos nuevas que suba el admin se perderán** si vuelves a desplegar. Para que los productos añadidos sobrevivan a los redeploys, en Railway puedes añadir un **Volume** (Settings → Volumes) y montar `/app/imagenes` y `tienda.db` ahí — pregúntame si quieres que te ayude a configurarlo.

## Personalizar

- **Radio de entrega**: cambia `RADIO_MAXIMO_KM` en `bot.py`.
- **Coordenadas del centro de Vinaròs**: `VINAROS_LAT` / `VINAROS_LON` en `bot.py`.
- **Teléfono de contacto**: `CONTACTO_TELEFONO` en `bot.py`.
- **Colores/pulseras de ejemplo iniciales**: `generar_imagenes.py` + lista `SEED_PRODUCTOS` en `bot.py`.
