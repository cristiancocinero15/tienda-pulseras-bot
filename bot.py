"""
Bot de Telegram - Tienda de Pulseras (con login de usuarios y panel admin)
---------------------------------------------------------------------------
- Registro de usuario al /start: si no existe, pide nombre de usuario.
  - Si el nombre es el del admin -> pide contraseña (ADMIN_PASSWORD, por variable de entorno).
  - Si el nombre ya está cogido -> sugiere uno libre (con número); si lo rechaza,
    se le indica que contacte con el admin para que se lo asignen.
- Catálogo dinámico guardado en base de datos (tienda.db).
- Solo el admin puede añadir productos: nombre, precio y foto. La foto se
  procesa automáticamente para quitar el fondo y ponerlo blanco.
- Los clientes solo pueden ver catálogo, carrito y hacer pedidos (no editan nada).
- Ubicación: se valida en silencio contra el radio de Vinaròs (1 km). Si no
  está dentro, se informa de que no se puede usar el servicio ahí y se da
  el contacto.

Variables de entorno necesarias:
    BOT_TOKEN         -> token de @BotFather
    PROVIDER_TOKEN     -> token de pagos (Stripe u otra pasarela)
    ADMIN_USERNAME     -> nombre de usuario del admin (ej. cristiancocinero15)
    ADMIN_PASSWORD     -> contraseña del admin (NUNCA la subas al código/GitHub)
"""

import io
import logging
import math
import os

from PIL import Image
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import db

try:
    from rembg import remove as rembg_remove
    REMBG_DISPONIBLE = True
except ImportError:
    REMBG_DISPONIBLE = False

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN", "")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cristiancocinero15")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
CONTACTO_TELEFONO = "614378910"

IMG_DIR = os.path.join(os.path.dirname(__file__), "imagenes")
os.makedirs(IMG_DIR, exist_ok=True)

VINAROS_LAT = 40.4676
VINAROS_LON = 0.4753
RADIO_MAXIMO_KM = 1.0

# Estados de conversación
(ASK_USERNAME, ASK_PASSWORD, CONFIRM_ALT_USERNAME,
 ADMIN_NOMBRE, ADMIN_PRECIO, ADMIN_FOTO) = range(6)


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------

def distancia_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def quitar_fondo_y_poner_blanco(imagen_bytes: bytes) -> bytes:
    """Quita el fondo de la foto del producto y lo sustituye por blanco."""
    if not REMBG_DISPONIBLE:
        return imagen_bytes
    try:
        recorte = rembg_remove(imagen_bytes)  # PNG con fondo transparente
        img = Image.open(io.BytesIO(recorte)).convert("RGBA")
        fondo_blanco = Image.new("RGBA", img.size, (255, 255, 255, 255))
        fondo_blanco.paste(img, (0, 0), img)
        salida = io.BytesIO()
        fondo_blanco.convert("RGB").save(salida, format="PNG")
        return salida.getvalue()
    except Exception as e:
        logger.warning("No se pudo quitar el fondo: %s", e)
        return imagen_bytes


def get_cart(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "cart" not in context.user_data:
        context.user_data["cart"] = {}
    return context.user_data["cart"]


def cart_total(cart: dict) -> float:
    total = 0.0
    for pid, qty in cart.items():
        prod = db.get_product(int(pid))
        if prod:
            total += prod["precio"] * qty
    return total


def menu_principal_kb(es_admin: bool) -> InlineKeyboardMarkup:
    filas = [
        [InlineKeyboardButton("🎨 Ver catálogo", callback_data="ver_catalogo")],
        [InlineKeyboardButton("🛒 Carrito", callback_data="ver_carrito")],
        [InlineKeyboardButton("📞 Contacto", callback_data="ver_contacto")],
    ]
    if es_admin:
        filas.append([InlineKeyboardButton("➕ Añadir producto (admin)", callback_data="admin_add")])
    return InlineKeyboardMarkup(filas)


async def enviar_menu(chat_id, context, es_admin, saludo=""):
    texto = saludo + "\n\n¿Qué quieres hacer?" if saludo else "¿Qué quieres hacer?"
    await context.bot.send_message(chat_id, texto, reply_markup=menu_principal_kb(es_admin))


# ---------------------------------------------------------------------
# Login / registro (/start)
# ---------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    usuario = db.get_user(telegram_id)

    if usuario:
        await enviar_menu(
            update.effective_chat.id, context, bool(usuario["is_admin"]),
            f"👋 ¡Hola de nuevo, {usuario['username']}!",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 Bienvenido a *Tienda de Pulseras*.\n\n"
        "Es tu primera vez aquí. Escribe el *nombre de usuario* que quieres usar:",
        parse_mode="Markdown",
    )
    return ASK_USERNAME


async def recibir_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    telegram_id = update.effective_user.id

    if username == ADMIN_USERNAME:
        if not ADMIN_PASSWORD:
            await update.message.reply_text(
                "⚠️ El admin todavía no ha configurado la contraseña (ADMIN_PASSWORD). "
                "Contacta con soporte."
            )
            return ConversationHandler.END
        context.user_data["pending_username"] = username
        await update.message.reply_text("🔒 Ese usuario es el admin. Escribe la contraseña:")
        return ASK_PASSWORD

    if db.username_exists(username):
        sugerido = db.sugerir_username_libre(username)
        context.user_data["pending_username"] = sugerido
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"✅ Usar {sugerido}", callback_data="alt_si")],
                [InlineKeyboardButton("❌ No, prefiero otro", callback_data="alt_no")],
            ]
        )
        await update.message.reply_text(
            f"Ese nombre ya está en uso. ¿Te vale *{sugerido}*?",
            parse_mode="Markdown",
            reply_markup=kb,
        )
        return CONFIRM_ALT_USERNAME

    db.create_user(telegram_id, username, is_admin=False)
    await enviar_menu(update.effective_chat.id, context, False, f"✅ Usuario *{username}* creado.")
    return ConversationHandler.END


async def recibir_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    telegram_id = update.effective_user.id
    username = context.user_data.get("pending_username")

    if password == ADMIN_PASSWORD:
        db.create_user(telegram_id, username, is_admin=True)
        await enviar_menu(update.effective_chat.id, context, True, "✅ Acceso de admin concedido.")
        return ConversationHandler.END

    await update.message.reply_text(
        "❌ Contraseña incorrecta. Escribe /start para volver a intentarlo."
    )
    return ConversationHandler.END


async def confirmar_username_alternativo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = update.effective_user.id

    if query.data == "alt_si":
        username = context.user_data.get("pending_username")
        db.create_user(telegram_id, username, is_admin=False)
        await context.bot.send_message(query.message.chat_id, f"✅ Usuario *{username}* creado.", parse_mode="Markdown")
        await enviar_menu(query.message.chat_id, context, False)
    else:
        await context.bot.send_message(
            query.message.chat_id,
            "De acuerdo, no se ha creado el usuario. Contacta con el admin "
            f"(@{ADMIN_USERNAME} · ☎️ {CONTACTO_TELEFONO}) para que te asigne uno. "
            "Cuando lo tengas, escribe /start otra vez.",
        )
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# ---------------------------------------------------------------------
# Catálogo / carrito
# ---------------------------------------------------------------------

async def mostrar_catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()

    productos = db.get_products()
    if not productos:
        await context.bot.send_message(chat_id, "Todavía no hay productos en el catálogo.")
        return

    await context.bot.send_message(chat_id, "Aquí tienes el catálogo 👇")
    for prod in productos:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"➕ Añadir · {prod['precio']:.2f}€", callback_data=f"add_{prod['id']}")]]
        )
        ruta = prod["imagen"]
        with open(ruta, "rb") as foto:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=foto,
                caption=f"*{prod['nombre']}*\n{prod['precio']:.2f}€",
                parse_mode="Markdown",
                reply_markup=kb,
            )
    await context.bot.send_message(chat_id, "Cuando termines, pulsa 🛒 para ver tu carrito.")


async def anadir_al_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.replace("add_", "")
    cart = get_cart(context)
    cart[pid] = cart.get(pid, 0) + 1
    prod = db.get_product(int(pid))
    await query.answer(f"Añadido: {prod['nombre']} ✅")


def texto_carrito(cart: dict) -> str:
    if not cart:
        return "Tu carrito está vacío 🛒"
    lineas = ["🛒 *Tu carrito:*\n"]
    for pid, qty in cart.items():
        prod = db.get_product(int(pid))
        if prod:
            lineas.append(f"• {prod['nombre']} x{qty} — {prod['precio'] * qty:.2f}€")
    lineas.append(f"\n*Total: {cart_total(cart):.2f}€*")
    return "\n".join(lineas)


async def ver_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = get_cart(context)

    botones = []
    if cart:
        botones.append([InlineKeyboardButton("🧾 Finalizar pedido", callback_data="checkout")])
        botones.append([InlineKeyboardButton("🗑️ Vaciar carrito", callback_data="vaciar_carrito")])
    botones.append([InlineKeyboardButton("🎨 Seguir comprando", callback_data="ver_catalogo")])

    await context.bot.send_message(
        query.message.chat_id, texto_carrito(cart), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def vaciar_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["cart"] = {}
    await query.answer("Carrito vaciado 🗑️")


async def ver_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        query.message.chat_id,
        f"📞 Contacto: {CONTACTO_TELEFONO}\n👤 Admin: @{ADMIN_USERNAME}",
    )


# --- Checkout / ubicación ---

async def pedir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cart = get_cart(context)
    if not cart:
        await query.answer("Tu carrito está vacío", show_alert=True)
        return
    await query.answer()

    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Enviar mi ubicación", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await context.bot.send_message(
        query.message.chat_id,
        "Para continuar, envía tu ubicación:",
        reply_markup=kb,
    )


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    dist = distancia_km(loc.latitude, loc.longitude, VINAROS_LAT, VINAROS_LON)

    # Comprobación silenciosa: no se avisa nada hasta tener el resultado.
    if dist > RADIO_MAXIMO_KM:
        await update.message.reply_text(
            "❌ Lo sentimos, no podemos entregar en tu ubicación. Solo repartimos "
            "en Vinaròs (hasta 1 km del centro).\n\n"
            f"Si tienes dudas, contacta al ☎️ {CONTACTO_TELEFONO}.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await update.message.reply_text("✅ ¡Estás dentro de la zona de reparto!", reply_markup=ReplyKeyboardRemove())
    await enviar_factura(update, context)


async def enviar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = get_cart(context)
    chat_id = update.message.chat_id

    if not PROVIDER_TOKEN:
        await context.bot.send_message(
            chat_id, "⚠️ El pago online todavía no está configurado (falta PROVIDER_TOKEN)."
        )
        return

    prices = []
    for pid, qty in cart.items():
        prod = db.get_product(int(pid))
        if prod:
            prices.append(LabeledPrice(prod["nombre"], int(prod["precio"] * qty * 100)))

    await context.bot.send_invoice(
        chat_id=chat_id,
        title="Pedido - Tienda de Pulseras",
        description=texto_carrito(cart).replace("*", ""),
        payload="pedido-tienda-pulseras",
        provider_token=PROVIDER_TOKEN,
        currency="EUR",
        prices=prices,
        start_parameter="tienda-pulseras",
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def pago_exitoso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cart"] = {}
    await update.message.reply_text("🎉 ¡Pago recibido! Pedido confirmado. Gracias por tu compra.")


# ---------------------------------------------------------------------
# Admin: añadir producto (nombre -> precio -> foto)
# ---------------------------------------------------------------------

async def es_admin(update: Update) -> bool:
    usuario = db.get_user(update.effective_user.id)
    return bool(usuario and usuario["is_admin"])


async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not await es_admin(update):
        await query.answer("Solo el admin puede añadir productos.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await context.bot.send_message(query.message.chat_id, "Nombre del nuevo producto:")
    return ADMIN_NOMBRE


async def admin_add_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nuevo_producto_nombre"] = update.message.text.strip()
    await update.message.reply_text("Precio (ej. 3.50):")
    return ADMIN_PRECIO


async def admin_add_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("Precio no válido, escribe solo un número, ej. 3.50:")
        return ADMIN_PRECIO
    context.user_data["nuevo_producto_precio"] = precio
    await update.message.reply_text(
        "Envía ahora la *foto* del producto (le pondré fondo blanco automáticamente):",
        parse_mode="Markdown",
    )
    return ADMIN_FOTO


async def admin_add_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    foto = update.message.photo[-1]
    archivo = await foto.get_file()
    datos = bytes(await archivo.download_as_bytearray())

    datos_procesados = quitar_fondo_y_poner_blanco(datos)

    nombre = context.user_data["nuevo_producto_nombre"]
    precio = context.user_data["nuevo_producto_precio"]

    nombre_archivo = f"{nombre.lower().replace(' ', '_')}_{foto.file_unique_id}.png"
    ruta = os.path.join(IMG_DIR, nombre_archivo)
    with open(ruta, "wb") as f:
        f.write(datos_procesados)

    db.add_product(nombre, precio, ruta)

    aviso_fondo = "" if REMBG_DISPONIBLE else "\n(No se pudo quitar el fondo automáticamente: falta la librería rembg)"
    await update.message.reply_text(
        f"✅ Producto *{nombre}* añadido al catálogo ({precio:.2f}€).{aviso_fondo}",
        parse_mode="Markdown",
    )
    return ConversationHandler.END


SEED_PRODUCTOS = [
    ("Pulsera clásica Negra", 2.50, "clasico_negro.png"),
    ("Pulsera clásica Blanca", 2.50, "clasico_blanco.png"),
    ("Pulsera clásica Roja", 2.50, "clasico_rojo.png"),
    ("Pulsera clásica Azul", 2.50, "clasico_azul.png"),
    ("Pulsera clásica Verde", 2.50, "clasico_verde.png"),
    ("Pulsera clásica Amarilla", 2.50, "clasico_amarillo.png"),
    ("Pulsera combinada Rojo/Blanco", 3.00, "combinado_rojo_blanco.png"),
    ("Pulsera combinada Azul/Amarillo", 3.00, "combinado_azul_amarillo.png"),
    ("Pulsera combinada Verde/Negro", 3.00, "combinado_verde_negro.png"),
    ("Pulsera combinada Arcoíris", 3.50, "combinado_arcoiris.png"),
]


def sembrar_catalogo_inicial():
    """Si la base de datos no tiene productos, carga las pulseras de ejemplo."""
    if db.contar_productos() > 0:
        return
    for nombre, precio, archivo in SEED_PRODUCTOS:
        ruta = os.path.join(IMG_DIR, archivo)
        if os.path.exists(ruta):
            db.add_product(nombre, precio, ruta)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    db.init_db()
    sembrar_catalogo_inicial()
    app = Application.builder().token(BOT_TOKEN).build()

    login_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_username)],
            ASK_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_password)],
            CONFIRM_ALT_USERNAME: [CallbackQueryHandler(confirmar_username_alternativo, pattern="^alt_")],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    admin_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^admin_add$")],
        states={
            ADMIN_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_nombre)],
            ADMIN_PRECIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_precio)],
            ADMIN_FOTO: [MessageHandler(filters.PHOTO, admin_add_foto)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(login_conv)
    app.add_handler(admin_add_conv)
    app.add_handler(CallbackQueryHandler(mostrar_catalogo, pattern="^ver_catalogo$"))
    app.add_handler(CallbackQueryHandler(ver_carrito, pattern="^ver_carrito$"))
    app.add_handler(CallbackQueryHandler(vaciar_carrito, pattern="^vaciar_carrito$"))
    app.add_handler(CallbackQueryHandler(ver_contacto, pattern="^ver_contacto$"))
    app.add_handler(CallbackQueryHandler(pedir_ubicacion, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(anadir_al_carrito, pattern="^add_"))
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, pago_exitoso))

    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()
