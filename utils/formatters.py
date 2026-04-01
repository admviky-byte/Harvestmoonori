# utils/formatters.py - Message text formatters for Harvest Kingdom (Bahasa Indonesia)

from datetime import datetime, timezone
from game.data import (
    CROPS, ANIMALS, BUILDINGS, UPGRADE_TOOLS, EXPANSION_TOOLS, CLEARING_TOOLS,
    OBSTACLES, get_item_emoji, get_item_name, get_xp_for_next_level, PROCESSED_EMOJI
)
from database.db import parse_json_field, get_display_name
from game.engine import fmt_time


def fmt_farm(user: dict, plots: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    level = user["level"]
    coins = user["coins"]
    xp = user["xp"]
    next_xp = get_xp_for_next_level(level)
    xp_bar = make_xp_bar(xp, next_xp, level)
    name = get_display_name(user)

    lines = [
        f"🏡 **Kebun {name}**",
        f"👑 Level {level}  💵 Rp{coins:,}  💎 {user['gems']} permata",
        f"📈 XP: {xp:,} / {next_xp:,}  {xp_bar}",
        "",
        f"🌾 **Lahan Pertanian** ({user['plots']} lahan):",
    ]

    for plot in plots:
        slot = plot["slot"]
        if plot["status"] == "empty":
            lines.append(f"  [{slot+1}] 🟩 Kosong — ketuk untuk menanam")
        elif plot["status"] == "growing":
            crop = CROPS.get(plot["crop"], {})
            ready_at = datetime.fromisoformat(plot["ready_at"])
            if ready_at.tzinfo is None:
                ready_at = ready_at.replace(tzinfo=timezone.utc)
            if now >= ready_at:
                lines.append(f"  [{slot+1}] ✅ {crop.get('emoji','🌱')} {crop.get('name', plot['crop'])} — **SIAP PANEN!**")
            else:
                remaining = int((ready_at - now).total_seconds())
                lines.append(f"  [{slot+1}] 🌱 {crop.get('emoji','🌱')} {crop.get('name', plot['crop'])} — ⏳ {fmt_time(remaining)}")
        else:
            lines.append(f"  [{slot+1}] ❓ {plot['status']}")

    silo = parse_json_field(user["silo_items"])
    lines.append(f"\n📦 Gudang: {sum(silo.values())}/{user['silo_cap']}  🏚 Lumbung: {sum(parse_json_field(user['barn_items']).values())}/{user['barn_cap']}")
    return "\n".join(lines)


def fmt_animals(user: dict, pens: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    lines = [f"🐾 **Kandang Hewan** ({user['animal_pens']} kandang):", ""]

    for pen in pens:
        slot = pen["slot"]
        if pen["status"] == "empty":
            lines.append(f"  [{slot+1}] 🟩 Kandang kosong — ketuk untuk beli hewan")
        elif pen["status"] == "producing":
            animal = ANIMALS.get(pen["animal"], {})
            ready_at = datetime.fromisoformat(pen["ready_at"])
            if ready_at.tzinfo is None:
                ready_at = ready_at.replace(tzinfo=timezone.utc)
            if now >= ready_at:
                lines.append(f"  [{slot+1}] ✅ {animal.get('emoji','🐾')} {animal.get('name', pen['animal'])} → {animal.get('prod_emoji','📦')} **SIAP AMBIL!**")
            else:
                remaining = int((ready_at - now).total_seconds())
                lines.append(f"  [{slot+1}] {animal.get('emoji','🐾')} {animal.get('name', pen['animal'])} → ⏳ {fmt_time(remaining)}")
        else:
            lines.append(f"  [{slot+1}] ❓ {pen['status']}")
    return "\n".join(lines)


def fmt_storage(user: dict, storage_type: str = "silo") -> str:
    if storage_type == "silo":
        items = parse_json_field(user["silo_items"])
        cap = user["silo_cap"]
        used = sum(items.values())
        level = user["silo_level"]
        title = f"🌾 **Gudang** (Level {level}) — {used}/{cap}"
    else:
        items = parse_json_field(user["barn_items"])
        cap = user["barn_cap"]
        used = sum(items.values())
        level = user["barn_level"]
        title = f"🏚 **Lumbung** (Level {level}) — {used}/{cap}"

    bar = make_capacity_bar(used, cap)
    lines = [title, bar, ""]

    if not items:
        lines.append("  (kosong)")
    else:
        for item_key, qty in sorted(items.items(), key=lambda x: -x[1]):
            emoji = get_item_emoji(item_key)
            name = get_item_name(item_key)
            lines.append(f"  {emoji} {name}: **{qty}**")
    return "\n".join(lines)


def fmt_factories(user: dict, buildings: list[dict]) -> str:
    now = datetime.now(timezone.utc)
    owned_keys = {b["building"] for b in buildings}

    if not owned_keys:
        lines = [
            "🏭 **Pabrik**",
            "",
            "Kamu belum punya pabrik!",
            "Beli pabrik pertamamu dari menu di bawah.",
        ]
    else:
        lines = ["🏭 **Pabrik**", ""]
        for bld_key in owned_keys:
            bld = BUILDINGS[bld_key]
            bld_slots = [b for b in buildings if b["building"] == bld_key]
            lines.append(f"{bld['emoji']} **{bld['name']}**")
            for s in bld_slots:
                slot_num = s["slot"] + 1
                if s["status"] == "idle":
                    lines.append(f"  Slot {slot_num}: 💤 Menganggur")
                elif s["status"] == "producing":
                    ready_at = datetime.fromisoformat(s["ready_at"])
                    if ready_at.tzinfo is None:
                        ready_at = ready_at.replace(tzinfo=timezone.utc)
                    if now >= ready_at:
                        emoji = PROCESSED_EMOJI.get(s["item"], "📦")
                        lines.append(f"  Slot {slot_num}: ✅ {emoji} {get_item_name(s['item'])} SIAP!")
                    else:
                        remaining = int((ready_at - now).total_seconds())
                        emoji = PROCESSED_EMOJI.get(s["item"], "📦")
                        lines.append(f"  Slot {slot_num}: ⏳ {emoji} {get_item_name(s['item'])} — {fmt_time(remaining)}")
    return "\n".join(lines)


def fmt_orders(orders: list[dict]) -> str:
    import json
    lines = ["🚚 **Pesanan Pengiriman** (9 slot)", "Selesaikan pesanan untuk dapat Rp & XP!", ""]
    if not orders:
        lines.append("Tidak ada pesanan aktif. Cek lagi nanti!")
    for i, order in enumerate(orders, 1):
        items = json.loads(order["items"])
        item_parts = []
        for item_key, qty in items.items():
            emoji = get_item_emoji(item_key)
            name = get_item_name(item_key)
            item_parts.append(f"{qty}x {emoji}{name}")
        lines.append(f"**Pesanan {i}** (Slot {order['slot']+1})")
        lines.append(f"  📋 {', '.join(item_parts)}")
        lines.append(f"  💵 Rp{order['reward_coins']:,}  ⭐ {order['reward_xp']} XP")
        lines.append("")
    return "\n".join(lines)


def fmt_market(listings: list[dict], page: int, total: int) -> str:
    lines = [
        "🏪 **Pasar Global**",
        f"📰 {total} item dijual | Halaman {page+1}",
        "",
    ]
    if not listings:
        lines.append("Belum ada barang dijual. Jadilah yang pertama berjualan!")
    for listing in listings:
        emoji = get_item_emoji(listing["item"])
        name = get_item_name(listing["item"])
        total_price = listing["price"] * listing["qty"]
        lines.append(f"{emoji} **{name}** x{listing['qty']}")
        lines.append(f"  💵 Rp{listing['price']:,}/satuan (Total: Rp{total_price:,}) | 👤 {listing['seller_name']}")
        lines.append("")
    lines.append("Ketuk item untuk membelinya.")
    return "\n".join(lines)


def fmt_profile(user: dict) -> str:
    name = get_display_name(user)
    level = user["level"]
    xp = user["xp"]
    next_xp = get_xp_for_next_level(level)
    xp_bar = make_xp_bar(xp, next_xp, level)

    # Rank medal
    rank_medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rank = user.get("rank")
    rank_text = f"  {rank_medals.get(rank, '')} Peringkat #{rank}" if rank else ""

    silo = parse_json_field(user["silo_items"])
    barn = parse_json_field(user["barn_items"])
    silo_used = sum(silo.values())
    barn_used = sum(barn.values())

    lines = [
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📊 **Profil — {name}**",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🪪 ID: `{user['user_id']}`{rank_text}",
        "",
        f"👑 **Level {level}**",
        f"📈 XP: {xp:,} / {next_xp:,}",
        f"   {xp_bar}",
        "",
        f"💵 **Uang:** Rp{user['coins']:,}",
        f"💎 **Permata:** {user['gems']}",
        "",
        f"🌾 **Total Panen:** {user['total_harvests']:,}",
        f"🚚 **Total Penjualan:** {user['total_sales']:,}",
        "",
        f"🌱 **Kebun:** {user['plots']} lahan",
        f"🐾 **Kandang:** {user['animal_pens']} kandang",
        f"📦 **Gudang:** Lv{user['silo_level']} ({silo_used}/{user['silo_cap']})",
        f"🏚 **Lumbung:** Lv{user['barn_level']} ({barn_used}/{user['barn_cap']})",
        "",
        f"📅 **Bergabung:** {user['created_at'][:10]}",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def fmt_leaderboard(users: list[dict], requester_id: int = None) -> str:
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "🏆 **LEADERBOARD — Harvest Kingdom**",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if not users:
        lines.append("Belum ada pemain.")
        return "\n".join(lines)

    for i, u in enumerate(users):
        medal = medals.get(i, f"#{i+1}")
        name = get_display_name(u)
        is_you = " ← 🫵 KAMU" if requester_id and u["user_id"] == requester_id else ""

        lines.append(
            f"{medal} **{name}**{is_you}\n"
            f"    👑 Lv{u['level']}  📈 {u['xp']:,} XP  💵 Rp{u['coins']:,}"
        )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("Naikkan level & XP untuk jadi #1!")
    return "\n".join(lines)


def fmt_help() -> str:
    return """
❓ **HARVEST KINGDOM — BANTUAN & TUTORIAL**

👋 Selamat datang, Petani! Ini cara bermainnya:

━━━━━━━━━━━━━━━━━━━━
🌾 **BERTANI (Kebun Saya)**
━━━━━━━━━━━━━━━━━━━━
1. Ketuk **🏠 Kebun Saya** untuk lihat lahanmu
2. Ketuk lahan kosong 🟩 untuk pilih tanaman
3. Tanaman butuh Rp untuk benih dan tumbuh seiring waktu
4. Saat tanaman ✅ SIAP, ketuk untuk panen
5. Hasil panen masuk ke **Gudang**
6. Gunakan **🌾 Panen Semua** untuk panen sekaligus!
7. 🎁 Ada 5% kesempatan dapat alat bonus saat panen!

━━━━━━━━━━━━━━━━━━━━
🐾 **HEWAN TERNAK**
━━━━━━━━━━━━━━━━━━━━
1. Ketuk **🐾 Hewan** untuk lihat kandangmu
2. Ketuk kandang kosong 🟩 untuk beli hewan
3. Hewan otomatis menghasilkan produk seiring waktu
4. Ketuk kandang ✅ untuk ambil produknya (Telur, Susu, dll.)
5. Produk masuk ke **Gudang**
6. Perluas kandang untuk tampung lebih banyak hewan!

━━━━━━━━━━━━━━━━━━━━
🏭 **PABRIK**
━━━━━━━━━━━━━━━━━━━━
1. Ketuk **🏭 Pabrik** untuk lihat/beli bangunan
2. Gunakan hasil panen + produk hewan untuk buat **Barang Olahan**
3. Barang olahan dijual dengan harga jauh lebih tinggi!
4. Barang masuk ke **Lumbung**
5. Setiap pabrik punya beberapa slot produksi

Contoh rantai produksi:
🌾 Gandum → 🏭 Bakeri → 🍞 Roti

━━━━━━━━━━━━━━━━━━━━
📦 **PENYIMPANAN**
━━━━━━━━━━━━━━━━━━━━
🌾 **Gudang**: Menyimpan hasil panen & produk hewan
🏚 **Lumbung**: Menyimpan barang olahan & alat
- Upgrade untuk tambah kapasitas
- Upgrade butuh alat khusus (didapat dari bonus panen!)

━━━━━━━━━━━━━━━━━━━━
🚚 **PESANAN TRUK**
━━━━━━━━━━━━━━━━━━━━
- Selalu ada 9 pesanan pengiriman aktif
- Setiap pesanan butuh item tertentu dari penyimpananmu
- Menyelesaikan pesanan dapat **Rp + XP**
- Pesanan otomatis diperbarui setelah selesai

━━━━━━━━━━━━━━━━━━━━
🏪 **PASAR GLOBAL**
━━━━━━━━━━━━━━━━━━━━
- Beli item dari pemain lain
- Jual itemmu: Penyimpanan → ketuk item → Pasang di Pasar
- Tentukan hargamu dan tunggu pembeli!
- Maksimal 5 listing sekaligus

━━━━━━━━━━━━━━━━━━━━
🗺️ **PERLUASAN LAHAN**
━━━━━━━━━━━━━━━━━━━━
- Lahan baru ada rintangannya (Pohon, Batu, Rawa)
- Gunakan alat pembersih (Kapak, Dinamit, Sekop) untuk membersihkan
- Alat pembersih didapat sebagai **item bonus** saat panen
- Setelah dibersihkan, lahan jadi lahan pertanian baru!
- Perluas kebun dengan **Surat Tanah + Palu + Patok**

━━━━━━━━━━━━━━━━━━━━
💵 **TIPS BERMAIN**
━━━━━━━━━━━━━━━━━━━━
✅ Ambil 🎁 **Hadiah Harian** setiap hari!
✅ Olah hasil panen jadi barang — harga jual lebih tinggi!
✅ Selesaikan pesanan truk untuk bonus Rp & XP
✅ Level lebih tinggi = tanaman & hewan langka terbuka
✅ Cek pasar untuk item murah!
✅ Simpan alat untuk upgrade penyimpanan!

━━━━━━━━━━━━━━━━━━━━
📋 **PERINTAH**
━━━━━━━━━━━━━━━━━━━━
/start — Menu utama
/farm — Ke kebun
/storage — Cek penyimpanan
/market — Pasar global
/orders — Pesanan pengiriman
/daily — Ambil hadiah harian
/profile — Lihat statistikmu
/leaderboard — Papan peringkat
/setname — Ganti nama tampilan
/help — Halaman bantuan ini

Selamat bercocok tanam! 🌾👑
"""


def make_xp_bar(xp: int, next_xp: int, level: int) -> str:
    if next_xp <= 0:
        return "[LEVEL MAKS]"
    filled = int((xp / next_xp) * 10)
    filled = min(10, max(0, filled))
    return "[" + "█" * filled + "░" * (10 - filled) + "]"


def make_capacity_bar(used: int, cap: int) -> str:
    if cap <= 0:
        return "[███████████] PENUH"
    pct = min(1.0, used / cap)
    filled = int(pct * 10)
    bar = "[" + "█" * filled + "░" * (10 - filled) + f"] {used}/{cap}"
    return bar

def fmt_tutorial() -> str:
    return """
📖 **TUTORIAL — Harvest Kingdom**
━━━━━━━━━━━━━━━━━━━━

Yo! Selamat datang di Harvest Kingdom! 🌾👑
Ini game farming seru langsung di Telegram.
Gw jelasin step by step ya, santai aja~

━━━━━━━━━━━━━━━━━━━━
🌱 **STEP 1: MULAI NANAM**
━━━━━━━━━━━━━━━━━━━━
Pertama-tama, lo harus nanam dulu bro!

1️⃣ Ketuk **🏠 Kebun Saya** di menu
2️⃣ Liat lahan kosong 🟩 → ketuk salah satu
3️⃣ Pilih tanaman — mulai dari **🌾 Wheat** aja (2 menit doang)
4️⃣ Tunggu sampe ada tanda ✅
5️⃣ Ketuk lagi buat **panen**, atau pencet **🌾 Panen Semua**
6️⃣ Hasil panen masuk ke **Gudang** lo

💡 _Tips: Tanam wheat terus-terusan buat naikin level cepet!_

━━━━━━━━━━━━━━━━━━━━
📈 **STEP 2: NAIKIN LEVEL**
━━━━━━━━━━━━━━━━━━━━
Level itu penting banget! Makin tinggi level, makin banyak yang kebuka.

Cara naikin level:
🌾 Panen tanaman → dapet XP
🚚 Selesaiin pesanan → dapet XP + Rp
🎁 Ambil hadiah harian → dapet XP + Rp

Level 2 → buka 🐔 Chicken + 🥕 Carrot
Level 3 → buka 🏭 Bakery
Level 5 → buka 🐄 Cow
Level 7 → buka 🐷 Pig
...dan seterusnya!

━━━━━━━━━━━━━━━━━━━━
🐾 **STEP 3: BELI HEWAN**
━━━━━━━━━━━━━━━━━━━━
Begitu level 2, langsung beli hewan!

1️⃣ Ketuk **🐾 Hewan** di menu
2️⃣ Ketuk kandang kosong 🟩
3️⃣ Pilih hewan (misal 🐔 Chicken — Rp150)
4️⃣ Tunggu sampe ✅ → ketuk buat ambil produknya
5️⃣ Atau pencet **🧺 Ambil Semua** biar gampang

Hewan ngasilin produk terus tanpa perlu ditanam ulang! 🔄

━━━━━━━━━━━━━━━━━━━━
🏭 **STEP 4: BANGUN PABRIK**
━━━━━━━━━━━━━━━━━━━━
Pabrik itu mesin uang lo bro! Olah bahan mentah jadi barang mahal 💰

Contoh:
🌾 3x Wheat → 🏭 Bakery → 🍞 Bread (jual Rp35!)
🥛 2x Milk → 🧈 Dairy → 🧈 Butter (jual Rp90!)

1️⃣ Ketuk **🏭 Pabrik** → beli pabrik
2️⃣ Pilih resep → bahan otomatis kepake
3️⃣ Tunggu selesai → ambil hasilnya
4️⃣ Jual di **📦 Penyimpanan** atau pasang di **🏪 Pasar**

━━━━━━━━━━━━━━━━━━━━
🚚 **STEP 5: SELESAIIN PESANAN**
━━━━━━━━━━━━━━━━━━━━
Pesanan = cara paling cuan dapet duit! 🤑

1️⃣ Ketuk **🚚 Pesanan**
2️⃣ Liat pesanan minta item apa
3️⃣ Kumpulin item-nya (tanam/panen/produksi)
4️⃣ Klik pesanan → otomatis delivered!
5️⃣ Dapet **Rp + XP** lumayan gede

Pesanan susah? Pencet **🔄 Refresh** (1x per 24 jam) buat ganti semua pesanan.

━━━━━━━━━━━━━━━━━━━━
🛒 **STEP 6: TOKO ALAT**
━━━━━━━━━━━━━━━━━━━━
Butuh alat buat upgrade gudang atau perluas lahan?

2 cara dapetin:
1️⃣ **Gratis** — tiap panen ada 5% chance dapet alat random
2️⃣ **Beli** — ketuk **🛒 Toko Alat** di menu, beli pake Rp

Alat yang sering dibutuhin:
📌 Nail + 🔧 Screw + 🪟 Wood Panel → upgrade Gudang
🔩 Bolt + 🪵 Plank + 🩹 Duct Tape → upgrade Lumbung
📜 Land Deed + 🪛 Mallet + 📍 Marker Stake → perluas kebun

━━━━━━━━━━━━━━━━━━━━
💵 **TIPS PRO BIAR CEPET KAYA**
━━━━━━━━━━━━━━━━━━━━
✅ Jangan lupa ambil **🎁 Hadiah Harian** setiap hari!
✅ Tanam wheat non-stop di awal (cepet, murah, dapet XP)
✅ Upgrade gudang ASAP biar muat banyak
✅ Bikin barang olahan — harga jual 3-5x lipat!
✅ Selesaiin pesanan = income paling gede
✅ Jual item mahal di **🏪 Pasar** ke pemain lain
✅ Cek pasar juga — kadang ada item murah!

━━━━━━━━━━━━━━━━━━━━
Gitu aja sih bro, gampang kan? 😎
Sekarang balik ke menu dan mulai farming! 🌾
"""
