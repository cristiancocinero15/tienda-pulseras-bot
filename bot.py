"""
Bot de Telegram - Tienda de Pulseras
-------------------------------------
- Catálogo con fotos (pulseras de goma, colores clásicos y combinados)
- Carrito de compra por usuario
- Botón/icono de carrito para ver el pedido en cualquier momento
- Solo se permite pedir si la ubicación enviada está a máximo 1 km
  del centro de Vinaròs (no se admite Peñíscola ni otras localidades)
- Pago online mediante Telegram Payments (necesitas un provider_token)

Requisitos:
    pip install python-telegram-bot --break-system-packages

Variables de entorno necesarias:
    BOT_TOKEN        -> token que te da @BotFather
    PROVIDER_TOKEN    -> token de pagos (Stripe u otra pasarela conectada
                          a tu bot vía @BotFather -> Payments)
"""

import logging
import math
import os

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
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PON_AQUI_TU_TOKEN")
PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN", "PON_AQUI_TU_PROVIDER_TOKEN")

IMG_DIR = os.path.join(os.path.dirname(__file__), "imagenes")

# --- Zona de reparto: solo Vinaròs, hasta 1 km del centro ---
VINAROS_LAT = 40.4676
VINAROS_LON = 0.4753
RADIO_MAXIMO_KM = 1.0

# --- Catálogo de productos ---
CATALOGO = {
    "clasico_negro": {"nombre": "Pulsera clásica Negra", "precio": 2.50, "img": "clasico_negro.png"},
    "clasico_blanco": {"nombre": "Pulsera clásica Blanca", "precio": 2.50, "img": "clasico_blanco.png"},
    "clasico_rojo": {"nombre": "Pulsera clásica Roja", "precio": 2.50, "img": "clasico_rojo.png"},
    "clasico_azul": {"nombre": "Pulsera clásica Azul", "precio": 2.50, "img": "clasico_azul.png"},
    "clasico_verde": {"nombre": "Pulsera clásica Verde", "precio": 2.50, "img": "clasico_verde.png"},
    "clasico_amarillo": {"nombre": "Pulsera clásica Amarilla", "precio": 2.50, "img": "clasico_amarillo.png"},
    "combinado_rojo_blanco": {"nombre": "Pulsera combinada Rojo/Blanco", "precio": 3.00, "img": "combinado_rojo_blanco.png"},
    "combinado_azul_amarillo": {"nombre": "Pulsera combinada Azul/Amarillo", "precio": 3.00, "img": "combinado_azul_amarillo.png"},
    "combinado_verde_negro": {"nombre": "Pulsera combinada Verde/Negro", "precio": 3.00, "img": "combinado_verde_negro.png"},
    "combinado_arcoiris": {"nombre": "Pulsera combinada Arcoíris", "precio": 3.50, "img": "combinado_arcoiris.png"},
}


def get_cart(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "cart" not in context.user_data:
        context.user_data["cart"] = {}
    return context.user_data["cart"]


def cart_total(cart: dict) -> float:
    return sum(CATALOGO[pid]["precio"] * qty for pid, qty in cart.items())


def menu_principal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎨 Ver catálogo", callback_data="ver_catalogo")],
            [InlineKeyboardButton("🛒 Carrito", callback_data="ver_carrito")],
        ]
    )


# ---------------------------------------------------------------------
# Comandos y handlers
# ---------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Bienvenido a *Tienda de Pulseras*!\n\n"
        "Pulseras de goma en colores clásicos y combinados. 🎨\n"
        "📍 Solo hacemos entregas en *Vinaròs* (hasta 1 km del centro).\n\n"
        "Elige una opción:",
        parse_mode="Markdown",
        reply_markup=menu_principal_kb(),
    )


async def mostrar_catalogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    await context.bot.send_message(chat_id, "Aquí tienes el catálogo 👇")

    for pid, prod in CATALOGO.items():
        ruta = os.path.join(IMG_DIR, prod["img"])
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"➕ Añadir · {prod['precio']:.2f}€", callback_data=f"add_{pid}")]]
        )
        with open(ruta, "rb") as foto:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=foto,
                caption=f"*{prod['nombre']}*\n{prod['precio']:.2f}€",
                parse_mode="Markdown",
                reply_markup=kb,
            )

    await context.bot.send_message(chat_id, "Cuando termines, pulsa 🛒 para ver tu carrito.", reply_markup=menu_principal_kb())


async def anadir_al_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.replace("add_", "")
    cart = get_cart(context)
    cart[pid] = cart.get(pid, 0) + 1
    await query.answer(f"Añadido: {CATALOGO[pid]['nombre']} ✅")


def texto_carrito(cart: dict) -> str:
    if not cart:
        return "Tu carrito está vacío 🛒"
    lineas = ["🛒 *Tu carrito:*\n"]
    for pid, qty in cart.items():
        prod = CATALOGO[pid]
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
        query.message.chat_id,
        texto_carrito(cart),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(botones),
    )


async def vaciar_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["cart"] = {}
    await query.answer("Carrito vaciado 🗑️")
    await context.bot.send_message(query.message.chat_id, "Carrito vaciado.", reply_markup=menu_principal_kb())


# --- Checkout: pedir ubicación antes de pagar ---

async def pedir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    cart = get_cart(context)
    if not cart:
        await query.answer("Tu carrito está vacío", show_alert=True)
        return
    await query.answer()

    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Enviar mi ubicación", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await context.bot.send_message(
        query.message.chat_id,
        "Solo entregamos en *Vinaròs* (hasta 1 km del centro).\n"
        "Por favor, envía tu ubicación para comprobar que estás dentro de la zona:",
        parse_mode="Markdown",
        reply_markup=kb,
    )


def distancia_km(lat1, lon1, lat2, lon2) -> float:
    """Distancia entre dos puntos GPS (fórmula de Haversine), en km."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    dist = distancia_km(loc.latitude, loc.longitude, VINAROS_LAT, VINAROS_LON)

    if dist > RADIO_MAXIMO_KM:
        await update.message.reply_text(
            f"❌ Lo sentimos, estás a {dist:.2f} km del centro de Vinaròs.\n"
            "Solo hacemos entregas en Vinaròs, hasta 1 km. No repartimos en "
            "Peñíscola ni otras localidades.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await update.message.reply_text(
        f"✅ Ubicación validada ({dist:.2f} km del centro). ¡Estás dentro de la zona!",
        reply_markup=ReplyKeyboardRemove(),
    )
    await enviar_factura(update, context)


# --- Pago ---

async def enviar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = get_cart(context)
    chat_id = update.message.chat_id

    prices = [
        LabeledPrice(CATALOGO[pid]["nombre"], int(CATALOGO[pid]["precio"] * qty * 100))
        for pid, qty in cart.items()
    ]

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
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def pago_exitoso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cart"] = {}
    await update.message.reply_text(
        "🎉 ¡Pago recibido! Tu pedido de pulseras está confirmado.\n"
        "Nos pondremos en contacto para coordinar la entrega en Vinaròs. ¡Gracias!"
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mostrar_catalogo, pattern="^ver_catalogo$"))
    app.add_handler(CallbackQueryHandler(ver_carrito, pattern="^ver_carrito$"))
    app.add_handler(CallbackQueryHandler(vaciar_carrito, pattern="^vaciar_carrito$"))
    app.add_handler(CallbackQueryHandler(pedir_ubicacion, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(anadir_al_carrito, pattern="^add_"))
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, pago_exitoso))

    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()
