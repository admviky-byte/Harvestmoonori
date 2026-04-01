# handlers/main_handlers.py - Core handlers for Harvest Kingdom

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db import get_or_create_user, get_setting, fetchone, fetchall, get_display_name, set_display_name, get_leaderboard, set_avatar, get_avatar
from game.engine import (
    get_plots, get_animal_pens, get_user_buildings, get_orders,
    plant_crop, harvest_crop, harvest_all,
    buy_animal, collect_animal, collect_all_animals,
    buy_building, start_production, collect_production,
    ensure_orders, fulfill_order, refresh_orders,
    get_market_listings, buy_from_market, list_item_on_market, remove_market_listing,
    get_obstacles, clear_obstacle,
    upgrade_silo, upgrade_barn, expand_farm, expand_animal_pens,
    sell_item, claim_daily, get_user_full, get_item_count,
    buy_tool
)
from utils.keyboards import (
    main_menu_keyboard, farm_keyboard, plant_keyboard, animals_keyboard,
    buy_animal_keyboard, factories_keyboard, factory_detail_keyboard,
    storage_keyboard, storage_items_keyboard, sell_keyboard,
    orders_keyboard, market_keyboard, land_keyboard, back_to_menu,
    profile_keyboard, leaderboard_keyboard, shop_keyboard
)
from utils.formatters import (
    fmt_farm, fmt_animals, fmt_storage, fmt_factories,
    fmt_orders, fmt_market, fmt_profile, fmt_help, fmt_leaderboard,
    fmt_tutorial
)
from database.db import parse_json_field

logger = logging.getLogger(__name__)

# Safe edit/send helpers
async def safe_edit(query, text: str, keyboard=None, parse_mode=ParseMode.MARKDOWN):
    try:
        await query.edit_message_text(
            text, reply_markup=keyboard, parse_mode=parse_mode,
            disable_web_page_preview=True
        )
    except Exception:
        try:
            await query.message.reply_text(
                text, reply_markup=keyboard, parse_mode=parse_mode,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"safe_edit failed: {e}")

async def safe_send(update: Update, text: str, keyboard=None):
    try:
        await update.message.reply_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"safe_send failed: {e}")

async def get_item_photo(item_key: str) -> str | None:
    """Get photo file_id for an item from game_settings."""
    photo_id = await get_setting(f"photo_{item_key}")
    return photo_id if photo_id else None

async def safe_send_photo(target, text: str, keyboard=None, photo_id: str = None):
    """Send photo with caption, fallback to text if no photo or error."""
    if not photo_id:
        # No photo, send as text
        if hasattr(target, "edit_message_text"):
            await safe_edit(target, text, keyboard)
        elif hasattr(target, "message") and target.message:
            await safe_send(target, text, keyboard)
        return

    try:
        if hasattr(target, "message") and target.message:
            # From callback query — delete old message, send new photo
            chat_id = target.message.chat_id
            try:
                await target.message.delete()
            except Exception:
                pass
            await target.message.get_bot().send_photo(
                chat_id=chat_id,
                photo=photo_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # From update.message
            await target.message.reply_photo(
                photo=photo_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"safe_send_photo failed: {e}, falling back to text")
        if hasattr(target, "edit_message_text"):
            await safe_edit(target, text, keyboard)
        elif hasattr(target, "message") and target.message:
            try:
                await target.message.reply_text(
                    text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass


# ─── START / MENU ─────────────────────────────────────────────────────────────

async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    maintenance = await get_setting("maintenance_mode", "0")
    
    # Check maintenance (skip for admin)
    import os
    admin_ids = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
    if maintenance == "1" and user.id not in admin_ids:
        await update.message.reply_text("🔧 Game sedang maintenance. Coba lagi nanti!")
        return

    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    name = get_display_name(db_user)
    welcome = await get_setting("welcome_message", "Selamat datang di Harvest Kingdom! 🌾👑")

    text = (
        f"{welcome}\n\n"
        f"👋 Halo, **{name}**!\n"
        f"👑 Level {db_user['level']}  💵 Rp{db_user['coins']:,}\n\n"
        f"Mau ngapain hari ini?"
    )
    await safe_send(update, text, main_menu_keyboard())

async def menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    name = get_display_name(db_user)

    text = (
        f"🏠 **Menu Utama**\n"
        f"👑 Level {db_user['level']}  💵 Rp{db_user['coins']:,}  💎 {db_user['gems']}\n\n"
        f"Mau ngapain hari ini, **{name}**?"
    )
    await safe_edit(query, text, main_menu_keyboard())


# ─── FARM ─────────────────────────────────────────────────────────────────────

async def farm_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    plots = await get_plots(user.id)
    text = fmt_farm(db_user, plots)
    await safe_edit(query, text, farm_keyboard(plots, db_user["level"]))

async def farm_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    plots = await get_plots(user.id)
    text = fmt_farm(db_user, plots)
    await safe_send(update, text, farm_keyboard(plots, db_user["level"]))

async def plot_plant_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot = int(query.data.split("_")[2])
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    await safe_edit(query, f"🌱 **Pilih tanaman untuk Lahan {slot+1}:**\n\n(Harga yang ditampilkan adalah biaya benih)", plant_keyboard(db_user["level"], slot))

async def plant_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    slot = int(parts[1])
    crop_key = "_".join(parts[2:])
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await plant_crop(user.id, slot, crop_key)
    if ok:
        plots = await get_plots(user.id)
        db_user = await get_user_full(user.id)
        full_text = msg + "\n\n" + fmt_farm(db_user, plots)
        photo_id = await get_item_photo(crop_key)
        if photo_id:
            await safe_send_photo(query, full_text, farm_keyboard(plots, db_user["level"]), photo_id)
        else:
            await safe_edit(query, full_text, farm_keyboard(plots, db_user["level"]))
    else:
        await query.answer(msg, show_alert=True)

async def plot_harvest_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot = int(query.data.split("_")[2])
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await harvest_crop(user.id, slot)
    if ok:
        db_user = await get_user_full(user.id)
        plots = await get_plots(user.id)
        await safe_edit(query, msg + "\n\n" + fmt_farm(db_user, plots), farm_keyboard(plots, db_user["level"]))
    else:
        await query.answer(msg, show_alert=True)

async def harvest_all_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    count, failed, _ = await harvest_all(user.id)
    db_user = await get_user_full(user.id)
    plots = await get_plots(user.id)
    if count > 0:
        msg = f"✅ Dipanen {count} tanaman!"
        if failed:
            msg += f" ({failed} gagal, penyimpanan mungkin penuh)"
    else:
        msg = "⏳ Belum ada tanaman yang siap panen."
    await safe_edit(query, msg + "\n\n" + fmt_farm(db_user, plots), farm_keyboard(plots, db_user["level"]))

async def expand_farm_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    ok, msg = await expand_farm(user.id)
    await query.answer(msg, show_alert=True)
    if ok:
        db_user = await get_user_full(user.id)
        plots = await get_plots(user.id)
        await safe_edit(query, fmt_farm(db_user, plots), farm_keyboard(plots, db_user["level"]))


# ─── ANIMALS ──────────────────────────────────────────────────────────────────

async def animals_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    pens = await get_animal_pens(user.id)
    text = fmt_animals(db_user, pens)
    await safe_edit(query, text, animals_keyboard(pens, db_user["level"]))

async def pen_buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot = int(query.data.split("_")[2])
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    await safe_edit(query, f"🐾 **Pilih hewan untuk Kandang {slot+1}:**", buy_animal_keyboard(db_user["level"], slot))

async def buyanimal_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    slot = int(parts[1])
    animal_key = "_".join(parts[2:])
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await buy_animal(user.id, slot, animal_key)
    if ok:
        db_user = await get_user_full(user.id)
        pens = await get_animal_pens(user.id)
        await safe_edit(query, msg + "\n\n" + fmt_animals(db_user, pens), animals_keyboard(pens, db_user["level"]))
    else:
        await query.answer(msg, show_alert=True)

async def pen_collect_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot = int(query.data.split("_")[2])
    user = query.from_user
    ok, msg = await collect_animal(user.id, slot)
    if ok:
        db_user = await get_user_full(user.id)
        pens = await get_animal_pens(user.id)
        await safe_edit(query, msg + "\n\n" + fmt_animals(db_user, pens), animals_keyboard(pens, db_user["level"]))
    else:
        await query.answer(msg, show_alert=True)

async def expand_pens_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    ok, msg = await expand_animal_pens(user.id)
    await query.answer(msg, show_alert=True)
    if ok:
        db_user = await get_user_full(user.id)
        pens = await get_animal_pens(user.id)
        await safe_edit(query, fmt_animals(db_user, pens), animals_keyboard(pens, db_user["level"]))

async def collect_all_animals_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    collected, failed, _ = await collect_all_animals(user.id)
    db_user = await get_user_full(user.id)
    pens = await get_animal_pens(user.id)
    if collected > 0:
        msg = f"✅ Diambil {collected} produk hewan!"
        if failed:
            msg += f" ({failed} gagal, gudang mungkin penuh)"
    else:
        msg = "⏳ Belum ada produk hewan yang siap diambil."
    await safe_edit(query, msg + "\n\n" + fmt_animals(db_user, pens), animals_keyboard(pens, db_user["level"]))


# ─── FACTORIES ────────────────────────────────────────────────────────────────

async def factories_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    buildings = await get_user_buildings(user.id)
    text = fmt_factories(db_user, buildings)
    await safe_edit(query, text, factories_keyboard(buildings, db_user["level"]))

async def buy_building_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    building_key = "_".join(query.data.split("_")[2:])
    user = query.from_user
    ok, msg = await buy_building(user.id, building_key)
    if ok:
        db_user = await get_user_full(user.id)
        buildings = await get_user_buildings(user.id)
        await safe_edit(query, msg + "\n\n" + fmt_factories(db_user, buildings), factories_keyboard(buildings, db_user["level"]))
    else:
        await query.answer(msg, show_alert=True)

async def factory_detail_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    building_key = "_".join(query.data.split("_")[1:])
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    buildings = await get_user_buildings(user.id)
    slots = [b for b in buildings if b["building"] == building_key]

    from game.data import BUILDINGS
    bld = BUILDINGS.get(building_key, {})
    text = f"{bld.get('emoji','🏭')} **{bld.get('name','Factory')}**\n\nPilih resep untuk diproduksi:"
    await safe_edit(query, text, factory_detail_keyboard(building_key, slots))

async def produce_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    building_key = parts[1]
    recipe_key = "_".join(parts[2:])
    user = query.from_user
    ok, msg = await start_production(user.id, building_key, recipe_key)
    if ok:
        buildings = await get_user_buildings(user.id)
        slots = [b for b in buildings if b["building"] == building_key]
        await safe_edit(query, msg, factory_detail_keyboard(building_key, slots))
    else:
        await query.answer(msg, show_alert=True)

async def collect_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    building_key = parts[1]
    slot = int(parts[2])
    user = query.from_user
    ok, msg = await collect_production(user.id, building_key, slot)
    if ok:
        buildings = await get_user_buildings(user.id)
        bld_slots = [b for b in buildings if b["building"] == building_key]
        await safe_edit(query, msg, factory_detail_keyboard(building_key, bld_slots))
    else:
        await query.answer(msg, show_alert=True)


# ─── STORAGE ──────────────────────────────────────────────────────────────────

async def storage_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    silo = parse_json_field(db_user["silo_items"])
    barn = parse_json_field(db_user["barn_items"])
    text = (
        f"📦 **Ringkasan Penyimpanan**\n\n"
        f"🌾 Gudang (Lv{db_user['silo_level']}): {sum(silo.values())}/{db_user['silo_cap']}\n"
        f"🏚 Lumbung (Lv{db_user['barn_level']}): {sum(barn.values())}/{db_user['barn_cap']}\n\n"
        f"Pilih penyimpanan untuk lihat item:"
    )
    await safe_edit(query, text, storage_keyboard())

async def storage_silo_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_user_full(user.id)
    text = fmt_storage(db_user, "silo")
    items = parse_json_field(db_user["silo_items"])
    await safe_edit(query, text, storage_items_keyboard(items, "silo"))

async def storage_barn_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_user_full(user.id)
    text = fmt_storage(db_user, "barn")
    items = parse_json_field(db_user["barn_items"])
    await safe_edit(query, text, storage_items_keyboard(items, "barn"))

async def storage_page_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    storage_type = parts[1]
    page = int(parts[3])
    user = query.from_user
    db_user = await get_user_full(user.id)
    if storage_type == "silo":
        items = parse_json_field(db_user["silo_items"])
        text = fmt_storage(db_user, "silo")
    else:
        items = parse_json_field(db_user["barn_items"])
        text = fmt_storage(db_user, "barn")
    await safe_edit(query, text, storage_items_keyboard(items, storage_type, page))

async def sell_menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_key = "_".join(query.data.split("_")[2:])
    user = query.from_user
    qty = await get_item_count(user.id, item_key)
    if qty == 0:
        await query.answer("Kamu tidak punya item ini!", show_alert=True)
        return
    from game.data import get_item_emoji, get_item_name, CROPS, BUILDINGS
    emoji = get_item_emoji(item_key)
    name = get_item_name(item_key)

    sell_price = 0
    if item_key in CROPS:
        sell_price = CROPS[item_key]["sell_price"]
    else:
        for bld in BUILDINGS.values():
            if item_key in bld["recipes"]:
                sell_price = bld["recipes"][item_key]["sell_price"]
                break

    price_line = f"💵 Harga jual: Rp{sell_price:,}/satuan" if sell_price else "⚠️ Tidak bisa dijual langsung (pasang di pasar saja)"
    text = f"{emoji} **{name}** (kamu punya: {qty})\n{price_line}"

    photo_id = await get_item_photo(item_key)
    if photo_id:
        await safe_send_photo(query, text, sell_keyboard(item_key, qty), photo_id)
    else:
        await safe_edit(query, text, sell_keyboard(item_key, qty))

async def sell_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    item_key = "_".join(parts[1:-1])
    qty = int(parts[-1])
    user = query.from_user
    ok, msg = await sell_item(user.id, item_key, qty)
    await query.answer(msg, show_alert=True)
    if ok:
        db_user = await get_user_full(user.id)
        silo = parse_json_field(db_user["silo_items"])
        barn = parse_json_field(db_user["barn_items"])
        text = (
            f"📦 **Ringkasan Penyimpanan**\n\n"
            f"🌾 Gudang (Lv{db_user['silo_level']}): {sum(silo.values())}/{db_user['silo_cap']}\n"
            f"🏚 Lumbung (Lv{db_user['barn_level']}): {sum(barn.values())}/{db_user['barn_cap']}\n\n"
            f"Pilih penyimpanan untuk lihat item:"
        )
        await safe_edit(query, text, storage_keyboard())

async def upgrade_silo_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    ok, msg = await upgrade_silo(user.id)
    await query.answer(msg, show_alert=True)
    if ok:
        db_user = await get_user_full(user.id)
        silo = parse_json_field(db_user["silo_items"])
        barn = parse_json_field(db_user["barn_items"])
        await safe_edit(query,
            f"📦 **Penyimpanan**\n🌾 Gudang: {sum(silo.values())}/{db_user['silo_cap']}\n🏚 Lumbung: {sum(barn.values())}/{db_user['barn_cap']}",
            storage_keyboard()
        )

async def upgrade_barn_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    ok, msg = await upgrade_barn(user.id)
    await query.answer(msg, show_alert=True)
    if ok:
        db_user = await get_user_full(user.id)
        silo = parse_json_field(db_user["silo_items"])
        barn = parse_json_field(db_user["barn_items"])
        await safe_edit(query,
            f"📦 **Penyimpanan**\n🌾 Gudang: {sum(silo.values())}/{db_user['silo_cap']}\n🏚 Lumbung: {sum(barn.values())}/{db_user['barn_cap']}",
            storage_keyboard()
        )


# ─── ORDERS ───────────────────────────────────────────────────────────────────

async def orders_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    await ensure_orders(user.id, db_user["level"])
    orders = await get_orders(user.id)
    text = fmt_orders(orders)
    await safe_edit(query, text, orders_keyboard(orders))

async def orders_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    await ensure_orders(user.id, db_user["level"])
    orders = await get_orders(user.id)
    text = fmt_orders(orders)
    await safe_send(update, text, orders_keyboard(orders))

async def fulfill_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[1])
    user = query.from_user
    ok, msg = await fulfill_order(user.id, order_id)
    if ok:
        db_user = await get_user_full(user.id)
        await ensure_orders(user.id, db_user["level"])
        orders = await get_orders(user.id)
        await safe_edit(query, msg + "\n\n" + fmt_orders(orders), orders_keyboard(orders))
    else:
        await query.answer(msg, show_alert=True)

async def refresh_orders_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await refresh_orders(user.id, db_user["level"])
    if ok:
        orders = await get_orders(user.id)
        await safe_edit(query, msg + "\n\n" + fmt_orders(orders), orders_keyboard(orders))
    else:
        await query.answer(msg, show_alert=True)


# ─── MARKET ───────────────────────────────────────────────────────────────────

async def market_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE, page: int = 0):
    if hasattr(update, "callback_query") and update.callback_query:
        query = update.callback_query
        await query.answer()
        send_fn = lambda t, k: safe_edit(query, t, k)
    else:
        send_fn = lambda t, k: safe_send(update, t, k)

    per_page = 9
    listings = await get_market_listings(page, per_page)
    from database.db import get_db, fetchone, fetchall
    async with get_db() as db:
        row = await fetchone(db, "SELECT COUNT(*) as c FROM market_listings")
        total = row["c"]

    text = fmt_market(listings, page, total)
    await send_fn(text, market_keyboard(listings, page, total, per_page))

async def market_page_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[2])
    per_page = 9
    listings = await get_market_listings(page, per_page)
    from database.db import get_db, fetchone, fetchall
    async with get_db() as db:
        row = await fetchone(db, "SELECT COUNT(*) as c FROM market_listings")
        total = row["c"]
    text = fmt_market(listings, page, total)
    await safe_edit(query, text, market_keyboard(listings, page, total, per_page))

async def market_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)
    per_page = 9
    listings = await get_market_listings(0, per_page)
    from database.db import get_db, fetchone, fetchall
    async with get_db() as db:
        row = await fetchone(db, "SELECT COUNT(*) as c FROM market_listings")
        total = row["c"]
    text = fmt_market(listings, 0, total)
    await safe_send(update, text, market_keyboard(listings, 0, total, per_page))

async def mkt_buy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    listing_id = int(query.data.split("_")[2])
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await buy_from_market(user.id, listing_id)
    await query.answer(msg, show_alert=True)
    if ok:
        listings = await get_market_listings(0, 9)
        from database.db import get_db, fetchone, fetchall
        async with get_db() as db:
            row = await fetchone(db, "SELECT COUNT(*) as c FROM market_listings")
            total = row["c"]
        await safe_edit(query, fmt_market(listings, 0, total), market_keyboard(listings, 0, total))

async def my_listings_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    from database.db import get_db, fetchone, fetchall
    async with get_db() as db:
        rows = await fetchall(db, 
            "SELECT * FROM market_listings WHERE seller_id = ?", (user.id,)
        )
        listings = [dict(r) for r in rows]

    if not listings:
        await safe_edit(query, "📭 Kamu tidak punya listing aktif.", back_to_menu())
        return

    from game.data import get_item_emoji, get_item_name
    buttons = []
    for l in listings:
        emoji = get_item_emoji(l["item"])
        name = get_item_name(l["item"])
        buttons.append([InlineKeyboardButton(
            f"❌ Hapus: {emoji}{name} x{l['qty']} @ Rp{l['price']:,}",
            callback_data=f"rmlist_{l['id']}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Kembali to Market", callback_data="market")])
    await safe_edit(query, "📋 **Listing Pasar Kamu** (ketuk untuk hapus):", InlineKeyboardMarkup(buttons))

async def rmlist_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    listing_id = int(query.data.split("_")[1])
    user = query.from_user
    ok, msg = await remove_market_listing(user.id, listing_id)
    await query.answer(msg, show_alert=True)

async def market_list_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_key = "_".join(query.data.split("_")[2:])
    ctx.user_data["listing_item"] = item_key
    from game.data import get_item_emoji, get_item_name
    emoji = get_item_emoji(item_key)
    name = get_item_name(item_key)
    qty = await get_item_count(query.from_user.id, item_key)
    await safe_edit(
        query,
        f"📢 **Pasarkan {emoji} {name} di Pasar**\nKamu punya: {qty}\n\nKirim pesan dengan format:\n`/listitem {item_key} <qty> <price>`\n\nExample: `/listitem {item_key} 5 50`",
        back_to_menu()
    )

async def listitem_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    args = ctx.args
    if len(args) < 3:
        await safe_send(update, "Cara pakai: `/listitem <item> <qty> <price>`\nExample: `/listitem wheat 10 5`")
        return
    item_key = args[0].lower()
    try:
        qty = int(args[1])
        price = int(args[2])
    except ValueError:
        await safe_send(update, "❌ Jumlah dan harga harus angka.")
        return

    seller_name = user.first_name or user.username or "Farmer"
    ok, msg = await list_item_on_market(user.id, seller_name, item_key, qty, price)
    await safe_send(update, msg)


# ─── LAND ─────────────────────────────────────────────────────────────────────

async def land_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    obstacles = await get_obstacles(user.id)
    plots = await get_plots(user.id)
    text = (
        f"🗺️ **Manajemen Lahan**\n"
        f"Lahan kebun: {db_user['plots']} | Kandang hewan: {db_user['animal_pens']}\n\n"
        f"Bersihkan rintangan untuk buka lahan baru!\n"
        f"Alat pembersih bisa drop saat panen (5% chance).\n\n"
        f"🪓 Rintangan yang perlu dibersihkan: {len(obstacles)}"
    )
    await safe_edit(query, text, land_keyboard(obstacles, plots))

async def clear_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot = int(query.data.split("_")[1])
    user = query.from_user
    ok, msg = await clear_obstacle(user.id, slot)
    await query.answer(msg, show_alert=True)
    if ok:
        obstacles = await get_obstacles(user.id)
        plots = await get_plots(user.id)
        db_user = await get_user_full(user.id)
        text = (
            f"🗺️ **Manajemen Lahan**\n"
            f"Lahan kebun: {db_user['plots']} | Obstacles: {len(obstacles)}"
        )
        await safe_edit(query, text, land_keyboard(obstacles, plots))


# ─── PROFILE / DAILY / HELP / LEADERBOARD / SETNAME ──────────────────────────

async def profile_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    # Get rank
    lb = await get_leaderboard(50)
    for i, u in enumerate(lb):
        if u["user_id"] == user.id:
            db_user["rank"] = i + 1
            break
    text = fmt_profile(db_user)
    avatar = await get_avatar(user.id)
    if avatar:
        await safe_send_photo(query, text, profile_keyboard(), avatar)
    else:
        await safe_edit(query, text, profile_keyboard())

async def profile_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    lb = await get_leaderboard(50)
    for i, u in enumerate(lb):
        if u["user_id"] == user.id:
            db_user["rank"] = i + 1
            break
    text = fmt_profile(db_user)
    avatar = await get_avatar(user.id)
    if avatar:
        try:
            await update.message.reply_photo(
                photo=avatar, caption=text,
                reply_markup=profile_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await safe_send(update, text, profile_keyboard())
    else:
        await safe_send(update, text, profile_keyboard())

async def leaderboard_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    users = await get_leaderboard(10)
    text = fmt_leaderboard(users, user.id)
    await safe_edit(query, text, leaderboard_keyboard())

async def leaderboard_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)
    users = await get_leaderboard(10)
    text = fmt_leaderboard(users, user.id)
    await safe_send(update, text, leaderboard_keyboard())

async def setname_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    name = get_display_name(db_user)
    await safe_edit(
        query,
        f"✏️ **Ganti Nama Tampilan**\n\n"
        f"Nama saat ini: **{name}**\n\n"
        f"Kirim nama baru kamu di chat (maks 20 karakter).\n"
        f"Atau ketik /setname <nama baru>\n\n"
        f"Contoh: `/setname PetaniHebat`",
        back_to_menu()
    )
    ctx.user_data["pending_action"] = "setname"


# ─── SET AVATAR ──────────────────────────────────────────────────────────────

async def setavatar_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    avatar = await get_avatar(user.id)
    status = "✅ Sudah di-set" if avatar else "❌ Belum ada"
    await safe_edit(
        query,
        f"🖼️ **Set Avatar Profil**\n\n"
        f"Status avatar: {status}\n\n"
        f"📸 **Kirim foto** ke chat ini untuk set sebagai avatar profilmu.\n\n"
        f"Atau ketik `/setavatar` lalu kirim foto.",
        back_to_menu()
    )
    ctx.user_data["pending_action"] = "setavatar"

async def setavatar_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Check if reply to photo
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
        await set_avatar(user.id, photo.file_id)
        await safe_send(update, "✅ Avatar profil berhasil di-set! Cek di /profile", back_to_menu())
        return
    # Check if message itself has photo
    if update.message.photo:
        photo = update.message.photo[-1]
        await set_avatar(user.id, photo.file_id)
        await safe_send(update, "✅ Avatar profil berhasil di-set! Cek di /profile", back_to_menu())
        return

    avatar = await get_avatar(user.id)
    status = "✅ Sudah di-set" if avatar else "❌ Belum ada"
    ctx.user_data["pending_action"] = "setavatar"
    await safe_send(
        update,
        f"🖼️ **Set Avatar Profil**\n\n"
        f"Status avatar: {status}\n\n"
        f"📸 Kirim foto ke chat ini untuk set sebagai avatar.",
    )

async def user_photo_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle photo input from users for setavatar."""
    action = ctx.user_data.get("pending_action")
    if action != "setavatar":
        return
    if not update.message.photo:
        return
    ctx.user_data.pop("pending_action", None)
    photo = update.message.photo[-1]
    user = update.effective_user
    await set_avatar(user.id, photo.file_id)
    await safe_send(update, "✅ Avatar profil berhasil di-set! Cek di /profile 🎉", back_to_menu())

async def setname_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username, user.first_name)
    args = ctx.args
    if not args:
        name = get_display_name(db_user)
        await safe_send(
            update,
            f"✏️ **Ganti Nama Tampilan**\n\n"
            f"Nama saat ini: **{name}**\n\n"
            f"Kirim: `/setname <nama baru>`\n"
            f"Contoh: `/setname PetaniHebat`",
            back_to_menu()
        )
        return
    new_name = " ".join(args).strip()
    if len(new_name) > 20:
        await safe_send(update, "❌ Nama terlalu panjang! Maksimal 20 karakter.")
        return
    if len(new_name) < 2:
        await safe_send(update, "❌ Nama terlalu pendek! Minimal 2 karakter.")
        return
    await set_display_name(user.id, new_name)
    await safe_send(update, f"✅ Nama berhasil diganti menjadi **{new_name}**!", back_to_menu())

async def user_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle text input for setname from regular users."""
    action = ctx.user_data.get("pending_action")
    if not action:
        return
    text = update.message.text.strip()

    if action == "setname":
        ctx.user_data.pop("pending_action", None)
        if len(text) > 20:
            await safe_send(update, "❌ Nama terlalu panjang! Maksimal 20 karakter.")
            return
        if len(text) < 2:
            await safe_send(update, "❌ Nama terlalu pendek! Minimal 2 karakter.")
            return
        user = update.effective_user
        await set_display_name(user.id, text)
        await safe_send(update, f"✅ Nama berhasil diganti menjadi **{text}**!", back_to_menu())

async def daily_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await claim_daily(user.id)
    await query.answer(msg, show_alert=True)
    if ok:
        db_user = await get_user_full(user.id)
        await safe_edit(query, fmt_profile(db_user), profile_keyboard())

async def daily_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await claim_daily(user.id)
    await safe_send(update, msg, back_to_menu())

async def help_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit(query, fmt_help(), back_to_menu())

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await safe_send(update, fmt_help(), back_to_menu())

# ─── TOKO ALAT ────────────────────────────────────────────────────────────────

async def shop_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🛒 **Toko Alat**\n\n"
        "Beli alat yang kamu butuhkan untuk upgrade & perluasan!\n"
        "Alat juga bisa didapat gratis dari bonus panen (5%).\n\n"
        "Ketuk alat untuk membeli:"
    )
    await safe_edit(query, text, shop_keyboard())

async def shop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛒 **Toko Alat**\n\n"
        "Beli alat yang kamu butuhkan untuk upgrade & perluasan!\n"
        "Alat juga bisa didapat gratis dari bonus panen (5%).\n\n"
        "Ketuk alat untuk membeli:"
    )
    await safe_send(update, text, shop_keyboard())

async def shopbuy_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tool_key = query.data.split("_", 1)[1]
    user = query.from_user
    await get_or_create_user(user.id, user.username, user.first_name)
    ok, msg = await buy_tool(user.id, tool_key, 1)
    await query.answer(msg, show_alert=True)
    if ok:
        text = (
            f"{msg}\n\n"
            "🛒 **Toko Alat** — mau beli lagi?"
        )
        await safe_edit(query, text, shop_keyboard())


# ─── TUTORIAL ─────────────────────────────────────────────────────────────────

async def tutorial_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await safe_edit(query, fmt_tutorial(), back_to_menu())

async def tutorial_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await safe_send(update, fmt_tutorial(), back_to_menu())


async def noop_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Tidak ada yang bisa dilakukan di sini!", show_alert=False)

async def locked_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🔒 Naik level untuk membuka ini!", show_alert=True)
