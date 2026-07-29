"""
====================================================================
  YIGITSCRIPT SECURITY — GELİŞMİŞ SUNUCU YÖNETİM BOTU (Render Uyumlu)
====================================================================
Prefix: ys!

Sistemler:
  - HGBB (Hoş Geldin / Giriş Onay Sistemi)              -> komutla kurulur
  - Otorol (Kendi kendine rol seçme, buton tabanlı)      -> komutla kurulur
  - Moderasyon: kick, ban, unban, timeout, uyarı, temizle,
    kanal kilitleme, slowmode, rol ver/al, nick değiştir
  - Güvenlik: anti-spam, anti-raid, anti-link, yasaklı
    kelime filtresi, anti mention-spam
  - Loglama: giriş/çıkış, mesaj silme/düzenleme, ban/kick/timeout,
    rol ve kanal değişiklikleri
  - Seviye / XP sistemi + liderlik tablosu
  - Ticket (destek talebi) sistemi
  - Çekiliş (giveaway) sistemi
  - Rotating status ("YigitScript Security", "ys!yardim" vb.)
  - Kategorili, buton/menü tabanlı ys!yardim menüsü

ÖNEMLİ — ARTIK HİÇBİR ID KODUN İÇİNDE SABİT DEĞİL:
  Kanal/rol ayarlarının hepsi Discord üzerinden, komut yazıp ardından
  #kanal veya @rol etiketleyerek yapılır. Örnek:

    ys!ayarla-log #log-kanali
    ys!ayarla-hgbb #giris-kanali @Doğrulanmamış @Üye
    ys!otorol-ekle 🎮 @Oyuncu Oyuncu

  Böylece bot birden fazla sunucuda da sorunsuz çalışır.

Kurulum (Render / lokal):
  1) pip install -U discord.py flask
  2) BOT_TOKEN ortam değişkenini ayarla
  3) Discord Developer Portal'da şu intent'leri AÇIK yap:
       - SERVER MEMBERS INTENT
       - MESSAGE CONTENT INTENT
  4) python guvenlik_bot.py
====================================================================
"""

import discord
from discord.ext import commands, tasks
import json
import os
import time
import random
import asyncio
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque

# ======================================================================
# FLASK (Render için Web Sunucusu — bot canlı kalsın diye)
# ======================================================================
try:
    from flask import Flask
except ImportError:
    import subprocess
    subprocess.check_call(['pip', 'install', 'Flask'])
    from flask import Flask

import threading

app = Flask(__name__)


@app.route('/')
def home():
    return "✅ YigitScript Security çalışıyor!"


@app.route('/health')
def health():
    return "OK", 200


def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)


threading.Thread(target=run_web, daemon=True).start()
print("🌐 Web sunucusu başlatıldı!")

# ======================================================================
# TOKEN
# ======================================================================
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    print("❌ BOT_TOKEN bulunamadi!")
    exit(1)

PREFIX = "ys!"

# ======================================================================
# GENEL GÜVENLİK AYARLARI (varsayılan - sunucuya özel de değiştirilebilir)
# ======================================================================
SPAM_MESSAGE_LIMIT = 5        # bu kadar mesaj
SPAM_TIME_WINDOW = 6          # bu kadar saniyede atılırsa spam sayılır
SPAM_TIMEOUT_MINUTES = 5
MENTION_SPAM_LIMIT = 5         # tek mesajda bu kadar mention -> spam
RAID_JOIN_LIMIT = 8
RAID_TIME_WINDOW = 15
DEFAULT_BANNED_WORDS = []      # her sunucu kendi listesini ekler

XP_MIN = 15
XP_MAX = 25
XP_COOLDOWN = 60               # saniye - bu sürede tekrar mesaj atarsa XP almaz

DB_FILE = "guvenlik_data.json"

# ======================================================================
# VERİTABANI (sunucu bazlı JSON)
# ======================================================================
def _default_guild_data():
    return {
        "unverified_role_id": None,
        "verified_role_id": None,
        "welcome_channel_id": None,
        "log_channel_id": None,
        "mod_role_id": None,
        "ticket_category_id": None,
        "ticket_log_channel_id": None,
        "ticket_counter": 0,
        "self_roles": {},          # {emoji: {"role_id": int, "name": str}}
        "banned_words": [],
        "lockdown": False,
        "verified_users": [],
        "warns": {},                # {user_id: [ {sebep, veren, tarih} ]}
        "xp": {},                   # {user_id: {"xp": int, "level": int}}
        "welcome_message": None,
        "goodbye_message": None,
    }


_db_cache = None


def load_db():
    global _db_cache
    if _db_cache is not None:
        return _db_cache
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            _db_cache = json.load(f)
    except Exception:
        _db_cache = {"guilds": {}}
    if "guilds" not in _db_cache:
        _db_cache["guilds"] = {}
    return _db_cache


def save_db(db=None):
    global _db_cache
    if db is not None:
        _db_cache = db
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(_db_cache, f, indent=2, ensure_ascii=False)


def get_guild_data(guild_id):
    db = load_db()
    gid = str(guild_id)
    if gid not in db["guilds"]:
        db["guilds"][gid] = _default_guild_data()
    else:
        # eski kayıtlarda eksik alan varsa tamamla
        defaults = _default_guild_data()
        for key, value in defaults.items():
            db["guilds"][gid].setdefault(key, value)
    return db["guilds"][gid]


def save_guild_data(guild_id, data):
    db = load_db()
    db["guilds"][str(guild_id)] = data
    save_db(db)


# ======================================================================
# BOT KURULUMU
# ======================================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

message_times = defaultdict(lambda: deque(maxlen=SPAM_MESSAGE_LIMIT))
join_times_by_guild = defaultdict(lambda: deque(maxlen=RAID_JOIN_LIMIT))
xp_cooldowns = {}   # (guild_id, user_id) -> son xp zamanı


# ======================================================================
# YARDIMCI FONKSİYONLAR
# ======================================================================
async def log_event(guild: discord.Guild, embed: discord.Embed):
    if not guild:
        return
    data = get_guild_data(guild.id)
    channel_id = data.get("log_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


def is_mod(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    data = get_guild_data(member.guild.id)
    mod_role_id = data.get("mod_role_id")
    if mod_role_id:
        role = discord.utils.get(member.roles, id=mod_role_id)
        return role is not None
    return False


def mod_only():
    async def predicate(ctx):
        if is_mod(ctx.author):
            return True
        await ctx.send("❌ Bu komutu kullanmak için yetkin yok.", delete_after=6)
        return False
    return commands.check(predicate)


def level_for_xp(xp: int) -> int:
    # basit seviye formülü: her seviye biraz daha fazla xp ister
    level = 0
    needed = 100
    remaining = xp
    while remaining >= needed:
        remaining -= needed
        level += 1
        needed += 50
    return level


def xp_for_next_level(level: int) -> int:
    total = 0
    needed = 100
    for _ in range(level):
        total += needed
        needed += 50
    return needed


# ======================================================================
# HGBB — GİRİŞ / DOĞRULAMA SİSTEMİ
# ======================================================================
class HGBBVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Doğrula ve Sunucuya Katıl", style=discord.ButtonStyle.success, custom_id="ys_hgbb_verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild
        data = get_guild_data(guild.id)

        verified_role = guild.get_role(data["verified_role_id"]) if data["verified_role_id"] else None
        unverified_role = guild.get_role(data["unverified_role_id"]) if data["unverified_role_id"] else None

        if not verified_role:
            await interaction.response.send_message(
                "⚠️ Üye rolü ayarlanmamış. Bir yetkilinin `ys!ayarla-hgbb` komutunu çalıştırması gerekiyor.",
                ephemeral=True,
            )
            return

        if verified_role in member.roles:
            await interaction.response.send_message("Zaten doğrulanmışsın! 🎉", ephemeral=True)
            return

        try:
            await member.add_roles(verified_role, reason="HGBB doğrulaması")
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="HGBB doğrulaması tamamlandı")
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Rol verme yetkim yok, bir yetkiliyle iletişime geçin.", ephemeral=True)
            return

        if member.id not in data["verified_users"]:
            data["verified_users"].append(member.id)
            save_guild_data(guild.id, data)

        await interaction.response.send_message("✅ Doğrulandın, sunucuya hoş geldin!", ephemeral=True)

        embed = discord.Embed(
            title="✅ Yeni Doğrulama",
            description=f"{member.mention} sunucuyu doğruladı.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        await log_event(guild, embed)


# ======================================================================
# OTOROL — KENDİ KENDİNE ROL SEÇME
# ======================================================================
class SelfRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id, name):
        super().__init__(
            label=name, emoji=emoji or None,
            style=discord.ButtonStyle.secondary,
            custom_id=f"ys_otorol_{role_id}",
        )
        self.role_id = int(role_id)
        self.role_name = name

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("⚠️ Bu rol artık mevcut değil.", ephemeral=True)
            return
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Otorol - kaldırıldı")
                await interaction.response.send_message(f"➖ **{self.role_name}** rolü kaldırıldı.", ephemeral=True)
            else:
                await member.add_roles(role, reason="Otorol - eklendi")
                await interaction.response.send_message(f"➕ **{self.role_name}** rolü verildi.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Bu rolü veremiyorum, rol hiyerarşisini kontrol edin.", ephemeral=True)


class SelfRoleView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        data = get_guild_data(guild_id)
        for emoji, info in data.get("self_roles", {}).items():
            self.add_item(SelfRoleButton(emoji, info["role_id"], info["name"]))


# ======================================================================
# TICKET SİSTEMİ
# ======================================================================
class TicketOpenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Destek Talebi Oluştur", style=discord.ButtonStyle.primary, custom_id="ys_ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        data = get_guild_data(guild.id)
        category = guild.get_channel(data["ticket_category_id"]) if data["ticket_category_id"] else None

        data["ticket_counter"] += 1
        ticket_no = data["ticket_counter"]
        save_guild_data(guild.id, data)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        mod_role_id = data.get("mod_role_id")
        if mod_role_id:
            mod_role = guild.get_role(mod_role_id)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            channel = await guild.create_text_channel(
                f"ticket-{ticket_no:04d}",
                category=category,
                overwrites=overwrites,
                reason=f"{interaction.user} destek talebi açtı",
            )
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Ticket kanalı oluşturamadım, yetkilerimi kontrol edin.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎫 Destek Talebi #{ticket_no:04d}",
            description=f"{interaction.user.mention}, talebini buradan yaz. Bir yetkili en kısa sürede yardımcı olacak.",
            color=discord.Color.blurple(),
        )
        await channel.send(embed=embed, view=TicketCloseView())
        await interaction.response.send_message(f"✅ Talebin oluşturuldu: {channel.mention}", ephemeral=True)


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Talebi Kapat", style=discord.ButtonStyle.danger, custom_id="ys_ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_mod(interaction.user) and interaction.user != interaction.channel.topic:
            pass  # herkes kapatabilir (isteğe göre kısıtlanabilir)
        await interaction.response.send_message("🔒 Bu talep 5 saniye içinde kapatılacak...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"{interaction.user} tarafından kapatıldı")
        except discord.Forbidden:
            pass


# ======================================================================
# YARDIM MENÜSÜ
# ======================================================================
class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Genel", emoji="ℹ️", value="genel"),
            discord.SelectOption(label="HGBB / Otorol", emoji="🚪", value="otorol"),
            discord.SelectOption(label="Moderasyon", emoji="🛡️", value="mod"),
            discord.SelectOption(label="Güvenlik Ayarları", emoji="🔒", value="guvenlik"),
            discord.SelectOption(label="Seviye Sistemi", emoji="⭐", value="seviye"),
            discord.SelectOption(label="Ticket", emoji="🎫", value="ticket"),
            discord.SelectOption(label="Çekiliş", emoji="🎉", value="cekilis"),
        ]
        super().__init__(placeholder="📂 Bir kategori seç...", options=options)

    async def callback(self, interaction: discord.Interaction):
        pages = {
            "genel": discord.Embed(
                title="ℹ️ Genel Komutlar",
                description=(
                    f"`{PREFIX}yardim` — Bu menüyü açar\n"
                    f"`{PREFIX}bilgi` — Sunucu ve bot hakkında bilgi verir\n"
                    f"`{PREFIX}ping` — Botun gecikmesini gösterir\n"
                    f"`{PREFIX}ayarlar` — Sunucunun mevcut yapılandırmasını gösterir"
                ),
                color=discord.Color.blurple(),
            ),
            "otorol": discord.Embed(
                title="🚪 HGBB & Otorol",
                description=(
                    f"`{PREFIX}ayarla-hgbb #kanal @doğrulanmamış-rol @üye-rol` *(yetkili)*\n"
                    f"`{PREFIX}hgbb-kur` *(yetkili)* — doğrulama mesajını bu kanala kurar\n"
                    f"`{PREFIX}otorol-ekle emoji @rol isim` *(yetkili)*\n"
                    f"`{PREFIX}otorol-kaldir emoji` *(yetkili)*\n"
                    f"`{PREFIX}otorol-kur` *(yetkili)* — rol seçim menüsünü bu kanala kurar"
                ),
                color=discord.Color.green(),
            ),
            "mod": discord.Embed(
                title="🛡️ Moderasyon",
                description=(
                    f"`{PREFIX}at @kullanıcı [sebep]` — sunucudan atar\n"
                    f"`{PREFIX}yasakla @kullanıcı [sebep]` — banlar\n"
                    f"`{PREFIX}yasak-kaldir kullanıcı_id` — ban kaldırır\n"
                    f"`{PREFIX}sustur @kullanıcı dakika [sebep]` — susturur (timeout)\n"
                    f"`{PREFIX}sustur-kaldir @kullanıcı` — susturmayı kaldırır\n"
                    f"`{PREFIX}uyar @kullanıcı [sebep]` — uyarı verir\n"
                    f"`{PREFIX}uyarilar @kullanıcı` — uyarı geçmişini gösterir\n"
                    f"`{PREFIX}temizle [adet]` — mesaj siler (maks. 100)\n"
                    f"`{PREFIX}kilitle` / `{PREFIX}kilit-ac` — kanalı kilitler/açar\n"
                    f"`{PREFIX}yavaslat saniye` — yavaş mod ayarlar\n"
                    f"`{PREFIX}rol-ver @kullanıcı @rol` / `{PREFIX}rol-al @kullanıcı @rol`"
                ),
                color=discord.Color.red(),
            ),
            "guvenlik": discord.Embed(
                title="🔒 Güvenlik Ayarları",
                description=(
                    f"`{PREFIX}ayarla-log #kanal` — log kanalını ayarlar\n"
                    f"`{PREFIX}mod-rol @rol` — yetkili rolünü ayarlar\n"
                    f"`{PREFIX}yasakli-ekle kelime` — yasaklı kelime ekler\n"
                    f"`{PREFIX}yasakli-sil kelime` — yasaklı kelime siler\n"
                    f"`{PREFIX}sunucu-kilitle` / `{PREFIX}sunucu-kilit-ac` — raid modunda tüm doğrulanmamış üyelerin mesajlarını engeller\n\n"
                    "**Otomatik korumalar:** anti-spam, anti-raid, anti-link, "
                    "mention-spam ve yasaklı kelime filtresi her zaman aktiftir."
                ),
                color=discord.Color.orange(),
            ),
            "seviye": discord.Embed(
                title="⭐ Seviye Sistemi",
                description=(
                    f"`{PREFIX}seviye [@kullanıcı]` — seviye/XP bilgisini gösterir\n"
                    f"`{PREFIX}liderlik` — sunucu liderlik tablosunu gösterir\n\n"
                    "Mesaj attıkça otomatik XP kazanılır (spam'i önlemek için kısa bir bekleme süresi vardır)."
                ),
                color=discord.Color.gold(),
            ),
            "ticket": discord.Embed(
                title="🎫 Ticket Sistemi",
                description=(
                    f"`{PREFIX}ayarla-ticket #kategori` — ticket kanallarının açılacağı kategoriyi ayarlar\n"
                    f"`{PREFIX}ticket-kur` *(yetkili)* — destek talebi oluşturma mesajını bu kanala kurar"
                ),
                color=discord.Color.teal(),
            ),
            "cekilis": discord.Embed(
                title="🎉 Çekiliş Sistemi",
                description=(
                    f"`{PREFIX}cekilis dakika ödül` *(yetkili)* — çekiliş başlatır, süre bitince 🎉 ile katılanlar arasından otomatik kazanan seçilir"
                ),
                color=discord.Color.magenta(),
            ),
        }
        await interaction.response.edit_message(embed=pages[self.values[0]], view=self.view)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())


@bot.command(name="yardim")
async def yardim(ctx):
    embed = discord.Embed(
        title="🛡️ YigitScript Security — Yardım Menüsü",
        description=(
            "Aşağıdaki menüden bir kategori seç.\n\n"
            "**Sistemler:** HGBB • Otorol • Moderasyon • Güvenlik • Seviye • Ticket • Çekiliş"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"Prefix: {PREFIX}  |  YigitScript Security")
    await ctx.send(embed=embed, view=HelpView())


# ======================================================================
# KURULUM / AYAR KOMUTLARI (yetkili)
# ======================================================================
@bot.command(name="ayarla-hgbb")
@commands.has_permissions(administrator=True)
async def ayarla_hgbb(ctx, kanal: discord.TextChannel, dogrulanmamis_rol: discord.Role, uye_rol: discord.Role):
    data = get_guild_data(ctx.guild.id)
    data["welcome_channel_id"] = kanal.id
    data["unverified_role_id"] = dogrulanmamis_rol.id
    data["verified_role_id"] = uye_rol.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(
        f"✅ HGBB ayarlandı!\n📢 Karşılama kanalı: {kanal.mention}\n"
        f"🔸 Doğrulanmamış rol: {dogrulanmamis_rol.mention}\n🔹 Üye rolü: {uye_rol.mention}"
    )


@bot.command(name="hgbb-kur")
@mod_only()
async def hgbb_kur(ctx):
    data = get_guild_data(ctx.guild.id)
    if not data["verified_role_id"]:
        await ctx.send(f"⚠️ Önce `{PREFIX}ayarla-hgbb #kanal @doğrulanmamış-rol @üye-rol` komutunu çalıştır.")
        return
    embed = discord.Embed(
        title="🚪 Sunucuya Hoş Geldin!",
        description=(
            "Sunucunun tüm kanallarını görebilmek için aşağıdaki butona basarak "
            "kendini doğrulaman gerekiyor.\n\nButona bastığında otomatik olarak üye rolün verilecek."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="YigitScript Security | HGBB")
    await ctx.send(embed=embed, view=HGBBVerifyView())
    await ctx.send("✅ Doğrulama mesajı bu kanala kuruldu.", delete_after=5)


@bot.command(name="ayarla-log")
@commands.has_permissions(administrator=True)
async def ayarla_log(ctx, kanal: discord.TextChannel):
    data = get_guild_data(ctx.guild.id)
    data["log_channel_id"] = kanal.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Log kanalı {kanal.mention} olarak ayarlandı.")


@bot.command(name="mod-rol")
@commands.has_permissions(administrator=True)
async def mod_rol(ctx, rol: discord.Role):
    data = get_guild_data(ctx.guild.id)
    data["mod_role_id"] = rol.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Yetkili rolü {rol.mention} olarak ayarlandı.")


@bot.command(name="otorol-ekle")
@commands.has_permissions(administrator=True)
async def otorol_ekle(ctx, emoji: str, rol: discord.Role, *, isim: str):
    data = get_guild_data(ctx.guild.id)
    data["self_roles"][emoji] = {"role_id": rol.id, "name": isim}
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Otorol eklendi: {emoji} → {rol.mention} ({isim})")


@bot.command(name="otorol-kaldir")
@commands.has_permissions(administrator=True)
async def otorol_kaldir(ctx, emoji: str):
    data = get_guild_data(ctx.guild.id)
    if emoji in data["self_roles"]:
        del data["self_roles"][emoji]
        save_guild_data(ctx.guild.id, data)
        await ctx.send(f"✅ {emoji} otorolü kaldırıldı.")
    else:
        await ctx.send("⚠️ Bu emoji ile kayıtlı bir otorol yok.")


@bot.command(name="otorol-kur")
@mod_only()
async def otorol_kur(ctx):
    data = get_guild_data(ctx.guild.id)
    if not data["self_roles"]:
        await ctx.send(f"⚠️ Henüz otorol eklenmemiş. Önce `{PREFIX}otorol-ekle emoji @rol isim` komutunu kullan.")
        return
    aciklama = "\n".join(f"{emoji} — **{info['name']}**" for emoji, info in data["self_roles"].items())
    embed = discord.Embed(
        title="🎭 Rol Seçimi",
        description=f"İlgilendiğin rolleri seçmek için aşağıdaki butonlara tıkla:\n\n{aciklama}",
        color=discord.Color.gold(),
    )
    await ctx.send(embed=embed, view=SelfRoleView(ctx.guild.id))
    await ctx.send("✅ Otorol menüsü bu kanala kuruldu.", delete_after=5)


@bot.command(name="yasakli-ekle")
@mod_only()
async def yasakli_ekle(ctx, *, kelime: str):
    data = get_guild_data(ctx.guild.id)
    kelime = kelime.lower().strip()
    if kelime not in data["banned_words"]:
        data["banned_words"].append(kelime)
        save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ `{kelime}` yasaklı kelime listesine eklendi.")


@bot.command(name="yasakli-sil")
@mod_only()
async def yasakli_sil(ctx, *, kelime: str):
    data = get_guild_data(ctx.guild.id)
    kelime = kelime.lower().strip()
    if kelime in data["banned_words"]:
        data["banned_words"].remove(kelime)
        save_guild_data(ctx.guild.id, data)
        await ctx.send(f"✅ `{kelime}` yasaklı kelime listesinden çıkarıldı.")
    else:
        await ctx.send("⚠️ Bu kelime listede yok.")


@bot.command(name="ayarla-ticket")
@commands.has_permissions(administrator=True)
async def ayarla_ticket(ctx, kategori: discord.CategoryChannel):
    data = get_guild_data(ctx.guild.id)
    data["ticket_category_id"] = kategori.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Ticket kategorisi **{kategori.name}** olarak ayarlandı.")


@bot.command(name="ticket-kur")
@mod_only()
async def ticket_kur(ctx):
    embed = discord.Embed(
        title="🎫 Destek Sistemi",
        description="Bir sorunun mu var? Aşağıdaki butona basarak özel bir destek talebi oluşturabilirsin.",
        color=discord.Color.teal(),
    )
    await ctx.send(embed=embed, view=TicketOpenView())
    await ctx.send("✅ Ticket mesajı bu kanala kuruldu.", delete_after=5)


@bot.command(name="ayarlar")
@mod_only()
async def ayarlar(ctx):
    data = get_guild_data(ctx.guild.id)
    g = ctx.guild

    def fmt_channel(cid):
        ch = g.get_channel(cid) if cid else None
        return ch.mention if ch else "Ayarlanmadı"

    def fmt_role(rid):
        role = g.get_role(rid) if rid else None
        return role.mention if role else "Ayarlanmadı"

    embed = discord.Embed(title="⚙️ Sunucu Ayarları", color=discord.Color.blurple())
    embed.add_field(name="Karşılama Kanalı", value=fmt_channel(data["welcome_channel_id"]), inline=True)
    embed.add_field(name="Log Kanalı", value=fmt_channel(data["log_channel_id"]), inline=True)
    embed.add_field(name="Doğrulanmamış Rol", value=fmt_role(data["unverified_role_id"]), inline=True)
    embed.add_field(name="Üye Rolü", value=fmt_role(data["verified_role_id"]), inline=True)
    embed.add_field(name="Yetkili Rolü", value=fmt_role(data["mod_role_id"]), inline=True)
    embed.add_field(name="Kilit Modu", value="🔒 Açık" if data["lockdown"] else "🔓 Kapalı", inline=True)
    embed.add_field(name="Otorol Sayısı", value=str(len(data["self_roles"])), inline=True)
    embed.add_field(name="Yasaklı Kelime Sayısı", value=str(len(data["banned_words"])), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="bilgi")
async def bilgi(ctx):
    data = get_guild_data(ctx.guild.id)
    embed = discord.Embed(title=f"📊 {ctx.guild.name}", color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👥 Üye Sayısı", value=str(ctx.guild.member_count), inline=True)
    embed.add_field(name="✅ Doğrulanan Üye", value=str(len(data["verified_users"])), inline=True)
    embed.add_field(name="📡 Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="🔒 Kilit Modu", value="Açık" if data["lockdown"] else "Kapalı", inline=True)
    embed.set_footer(text="YigitScript Security")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")


# ======================================================================
# MODERASYON KOMUTLARI
# ======================================================================
@bot.command(name="at")
@mod_only()
async def kick_cmd(ctx, kullanici: discord.Member, *, sebep: str = "Belirtilmedi"):
    try:
        await kullanici.kick(reason=f"{ctx.author}: {sebep}")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu kullanıcıyı atma yetkim yok.")
        return
    await ctx.send(f"👢 {kullanici.mention} sunucudan atıldı. Sebep: {sebep}")
    embed = discord.Embed(title="👢 Üye Atıldı", color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Kullanıcı", value=str(kullanici), inline=True)
    embed.add_field(name="Yetkili", value=ctx.author.mention, inline=True)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    await log_event(ctx.guild, embed)


@bot.command(name="yasakla")
@mod_only()
async def ban_cmd(ctx, kullanici: discord.Member, *, sebep: str = "Belirtilmedi"):
    try:
        await kullanici.ban(reason=f"{ctx.author}: {sebep}")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu kullanıcıyı banlama yetkim yok.")
        return
    await ctx.send(f"🔨 {kullanici.mention} banlandı. Sebep: {sebep}")
    embed = discord.Embed(title="🔨 Üye Banlandı", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Kullanıcı", value=str(kullanici), inline=True)
    embed.add_field(name="Yetkili", value=ctx.author.mention, inline=True)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    await log_event(ctx.guild, embed)


@bot.command(name="yasak-kaldir")
@mod_only()
async def unban_cmd(ctx, kullanici_id: int):
    try:
        user = await bot.fetch_user(kullanici_id)
        await ctx.guild.unban(user)
    except discord.NotFound:
        await ctx.send("⚠️ Bu ID ile banlı bir kullanıcı bulunamadı.")
        return
    except discord.Forbidden:
        await ctx.send("⚠️ Ban kaldırma yetkim yok.")
        return
    await ctx.send(f"✅ {user} adlı kullanıcının banı kaldırıldı.")
    embed = discord.Embed(title="✅ Ban Kaldırıldı", description=str(user), color=discord.Color.green())
    await log_event(ctx.guild, embed)


@bot.command(name="sustur")
@mod_only()
async def timeout_cmd(ctx, kullanici: discord.Member, dakika: int, *, sebep: str = "Belirtilmedi"):
    try:
        await kullanici.timeout(timedelta(minutes=dakika), reason=f"{ctx.author}: {sebep}")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu kullanıcıyı susturamıyorum.")
        return
    await ctx.send(f"🔇 {kullanici.mention} {dakika} dakika susturuldu. Sebep: {sebep}")
    embed = discord.Embed(title="🔇 Üye Susturuldu", color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Kullanıcı", value=str(kullanici), inline=True)
    embed.add_field(name="Süre", value=f"{dakika} dakika", inline=True)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    await log_event(ctx.guild, embed)


@bot.command(name="sustur-kaldir")
@mod_only()
async def remove_timeout_cmd(ctx, kullanici: discord.Member):
    try:
        await kullanici.timeout(None, reason=f"{ctx.author} tarafından kaldırıldı")
    except discord.Forbidden:
        await ctx.send("⚠️ Susturmayı kaldıramıyorum.")
        return
    await ctx.send(f"🔊 {kullanici.mention} kullanıcısının susturması kaldırıldı.")


@bot.command(name="uyar")
@mod_only()
async def warn_cmd(ctx, kullanici: discord.Member, *, sebep: str = "Belirtilmedi"):
    data = get_guild_data(ctx.guild.id)
    uid = str(kullanici.id)
    data["warns"].setdefault(uid, []).append({
        "sebep": sebep, "veren": ctx.author.id, "tarih": datetime.now(timezone.utc).isoformat(),
    })
    save_guild_data(ctx.guild.id, data)
    toplam = len(data["warns"][uid])

    await ctx.send(f"⚠️ {kullanici.mention} uyarıldı. (Toplam uyarı: {toplam}) Sebep: {sebep}")
    embed = discord.Embed(title="⚠️ Kullanıcı Uyarıldı", color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Kullanıcı", value=kullanici.mention, inline=True)
    embed.add_field(name="Yetkili", value=ctx.author.mention, inline=True)
    embed.add_field(name="Toplam Uyarı", value=str(toplam), inline=True)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    await log_event(ctx.guild, embed)

    if toplam >= 3:
        try:
            await kullanici.timeout(timedelta(hours=1), reason="3 uyarıya ulaştı (otomatik)")
            await ctx.send(f"🔇 {kullanici.mention} 3 uyarıya ulaştığı için otomatik olarak 1 saat susturuldu.")
        except discord.Forbidden:
            pass


@bot.command(name="uyarilar")
@mod_only()
async def warns_cmd(ctx, kullanici: discord.Member):
    data = get_guild_data(ctx.guild.id)
    uid = str(kullanici.id)
    uyarilar = data["warns"].get(uid, [])
    if not uyarilar:
        await ctx.send(f"✅ {kullanici.mention} kullanıcısının hiç uyarısı yok.")
        return
    embed = discord.Embed(title=f"⚠️ {kullanici} — Uyarı Geçmişi", color=discord.Color.orange())
    for i, w in enumerate(uyarilar, 1):
        tarih = datetime.fromisoformat(w["tarih"]).strftime("%d.%m.%Y %H:%M")
        embed.add_field(name=f"#{i} — {tarih}", value=w["sebep"], inline=False)
    await ctx.send(embed=embed)


@bot.command(name="temizle")
@mod_only()
async def clear_cmd(ctx, adet: int = 10):
    adet = max(1, min(adet, 100))
    deleted = await ctx.channel.purge(limit=adet + 1)  # +1 komut mesajının kendisi
    msg = await ctx.send(f"🗑️ {len(deleted) - 1} mesaj silindi.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except discord.NotFound:
        pass
    embed = discord.Embed(
        title="🗑️ Mesaj Temizleme",
        description=f"{ctx.author.mention} {ctx.channel.mention} kanalında **{len(deleted) - 1}** mesaj sildi.",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    )
    await log_event(ctx.guild, embed)


@bot.command(name="kilitle")
@mod_only()
async def lock_channel(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Bu kanal kilitlendi.")


@bot.command(name="kilit-ac")
@mod_only()
async def unlock_channel(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send("🔓 Bu kanalın kilidi açıldı.")


@bot.command(name="yavaslat")
@mod_only()
async def slowmode_cmd(ctx, saniye: int):
    saniye = max(0, min(saniye, 21600))
    await ctx.channel.edit(slowmode_delay=saniye)
    if saniye == 0:
        await ctx.send("✅ Yavaş mod kapatıldı.")
    else:
        await ctx.send(f"🐢 Yavaş mod {saniye} saniye olarak ayarlandı.")


@bot.command(name="rol-ver")
@mod_only()
async def give_role_cmd(ctx, kullanici: discord.Member, rol: discord.Role):
    try:
        await kullanici.add_roles(rol, reason=f"{ctx.author} tarafından verildi")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu rolü veremiyorum, rol hiyerarşisini kontrol et.")
        return
    await ctx.send(f"✅ {kullanici.mention} kullanıcısına {rol.mention} rolü verildi.")


@bot.command(name="rol-al")
@mod_only()
async def remove_role_cmd(ctx, kullanici: discord.Member, rol: discord.Role):
    try:
        await kullanici.remove_roles(rol, reason=f"{ctx.author} tarafından alındı")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu rolü alamıyorum, rol hiyerarşisini kontrol et.")
        return
    await ctx.send(f"✅ {kullanici.mention} kullanıcısından {rol.mention} rolü alındı.")


@bot.command(name="sunucu-kilitle")
@commands.has_permissions(administrator=True)
async def guild_lockdown_on(ctx):
    data = get_guild_data(ctx.guild.id)
    data["lockdown"] = True
    save_guild_data(ctx.guild.id, data)
    await ctx.send("🔒 Sunucu kilit moduna alındı. Doğrulanmamış üyelerin mesajları otomatik silinecek.")
    embed = discord.Embed(title="🔒 Kilitleme Aktif", description=f"{ctx.author.mention} sunucuyu kilitledi.", color=discord.Color.red())
    await log_event(ctx.guild, embed)


@bot.command(name="sunucu-kilit-ac")
@commands.has_permissions(administrator=True)
async def guild_lockdown_off(ctx):
    data = get_guild_data(ctx.guild.id)
    data["lockdown"] = False
    save_guild_data(ctx.guild.id, data)
    await ctx.send("🔓 Kilit modu kapatıldı.")
    embed = discord.Embed(title="🔓 Kilitleme Kaldırıldı", description=f"{ctx.author.mention} kilidi kaldırdı.", color=discord.Color.green())
    await log_event(ctx.guild, embed)


@bot.command(name="nick")
@mod_only()
async def nick_cmd(ctx, kullanici: discord.Member, *, yeni_isim: str):
    try:
        await kullanici.edit(nick=yeni_isim, reason=f"{ctx.author} tarafından değiştirildi")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu kullanıcının ismini değiştiremiyorum.")
        return
    await ctx.send(f"✅ {kullanici.mention} kullanıcısının ismi değiştirildi.")


# ======================================================================
# SEVİYE / XP SİSTEMİ
# ======================================================================
@bot.command(name="seviye")
async def seviye_cmd(ctx, kullanici: discord.Member = None):
    kullanici = kullanici or ctx.author
    data = get_guild_data(ctx.guild.id)
    info = data["xp"].get(str(kullanici.id), {"xp": 0, "level": 0})
    xp = info["xp"]
    level = level_for_xp(xp)
    ihtiyac = xp_for_next_level(level)
    onceki_toplam = ihtiyac - (100 + level * 50)

    embed = discord.Embed(title=f"⭐ {kullanici.display_name} — Seviye Kartı", color=discord.Color.gold())
    embed.set_thumbnail(url=kullanici.display_avatar.url)
    embed.add_field(name="Seviye", value=str(level), inline=True)
    embed.add_field(name="Toplam XP", value=str(xp), inline=True)
    embed.add_field(name="Sonraki Seviyeye Kalan", value=f"{max(ihtiyac - xp, 0)} XP", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="liderlik")
async def leaderboard_cmd(ctx):
    data = get_guild_data(ctx.guild.id)
    siralanmis = sorted(data["xp"].items(), key=lambda kv: kv[1]["xp"], reverse=True)[:10]
    if not siralanmis:
        await ctx.send("Henüz kimse XP kazanmamış.")
        return
    aciklama = ""
    madalyalar = ["🥇", "🥈", "🥉"]
    for i, (uid, info) in enumerate(siralanmis):
        madalya = madalyalar[i] if i < 3 else f"#{i + 1}"
        uye = ctx.guild.get_member(int(uid))
        isim = uye.display_name if uye else f"Kullanıcı {uid}"
        aciklama += f"{madalya} **{isim}** — {info['xp']} XP (Seviye {level_for_xp(info['xp'])})\n"
    embed = discord.Embed(title=f"🏆 {ctx.guild.name} — Liderlik Tablosu", description=aciklama, color=discord.Color.gold())
    await ctx.send(embed=embed)


# ======================================================================
# ÇEKİLİŞ (GIVEAWAY) SİSTEMİ
# ======================================================================
@bot.command(name="cekilis")
@mod_only()
async def giveaway_cmd(ctx, dakika: int, *, odul: str):
    bitis = datetime.now(timezone.utc) + timedelta(minutes=dakika)
    embed = discord.Embed(
        title="🎉 ÇEKİLİŞ BAŞLADI!",
        description=f"**Ödül:** {odul}\n\nKatılmak için 🎉 ile tepki ver!\n**Bitiş:** {dakika} dakika sonra",
        color=discord.Color.magenta(),
    )
    embed.set_footer(text=f"Başlatan: {ctx.author}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    await asyncio.sleep(dakika * 60)

    try:
        msg = await ctx.channel.fetch_message(msg.id)
    except discord.NotFound:
        return

    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    katilimcilar = []
    if reaction:
        async for user in reaction.users():
            if not user.bot:
                katilimcilar.append(user)

    if not katilimcilar:
        await ctx.send(f"🎉 Çekiliş sona erdi ama kimse katılmamış! Ödül: **{odul}**")
        return

    kazanan = random.choice(katilimcilar)
    sonuc_embed = discord.Embed(
        title="🎉 ÇEKİLİŞ SONA ERDİ!",
        description=f"**Ödül:** {odul}\n**Kazanan:** {kazanan.mention}\n\nTebrikler! 🎊",
        color=discord.Color.green(),
    )
    await ctx.send(embed=sonuc_embed)


# ======================================================================
# ROTATING STATUS
# ======================================================================
STATUS_MESSAGES = [
    ("watching", "YigitScript Security 🛡️"),
    ("listening", f"{PREFIX}yardim"),
    ("watching", "sunucunu koruyorum"),
    ("competing", "anti-raid & anti-spam"),
]


@tasks.loop(seconds=15)
async def status_loop():
    index = status_loop.current_loop % len(STATUS_MESSAGES)
    kind, text = STATUS_MESSAGES[index]
    activity_types = {
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing,
        "playing": discord.ActivityType.playing,
    }
    await bot.change_presence(activity=discord.Activity(type=activity_types[kind], name=text))


# ======================================================================
# OLAYLAR
# ======================================================================
@bot.event
async def on_ready():
    print(f"✅ Bot hazır! {bot.user}")
    print(f"📊 {len(bot.guilds)} sunucuda aktif")

    # Kalıcı (persistent) view'ları yeniden ekle
    bot.add_view(HGBBVerifyView())
    bot.add_view(TicketOpenView())
    bot.add_view(TicketCloseView())
    db = load_db()
    for gid in db.get("guilds", {}):
        try:
            bot.add_view(SelfRoleView(int(gid)))
        except Exception as e:
            print(f"⚠️ Otorol view yüklenemedi ({gid}): {e}")

    if not status_loop.is_running():
        status_loop.start()


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    data = get_guild_data(guild.id)
    now = time.time()
    joins = join_times_by_guild[guild.id]
    joins.append(now)

    if len(joins) == RAID_JOIN_LIMIT and (now - joins[0]) <= RAID_TIME_WINDOW and not data["lockdown"]:
        data["lockdown"] = True
        save_guild_data(guild.id, data)
        embed = discord.Embed(
            title="🚨 OLASI RAID TESPİT EDİLDİ",
            description=f"Son {RAID_TIME_WINDOW} saniyede {RAID_JOIN_LIMIT} üye katıldı. Sunucu otomatik olarak kilitlendi.",
            color=discord.Color.dark_red(),
        )
        await log_event(guild, embed)

    unverified_role = guild.get_role(data["unverified_role_id"]) if data["unverified_role_id"] else None
    if unverified_role:
        try:
            await member.add_roles(unverified_role, reason="HGBB - yeni üye")
        except discord.Forbidden:
            pass

    welcome_channel = guild.get_channel(data["welcome_channel_id"]) if data["welcome_channel_id"] else None
    if welcome_channel:
        embed = discord.Embed(
            title="👋 Aramıza Hoş Geldin!",
            description=f"{member.mention}, sunucuyu tam olarak kullanabilmek için doğrulama butonuna basmayı unutma.",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await welcome_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    log_embed = discord.Embed(title="📥 Üye Katıldı", description=f"{member.mention} ({member.id})", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
    await log_event(guild, log_embed)


@bot.event
async def on_member_remove(member: discord.Member):
    embed = discord.Embed(title="📤 Üye Ayrıldı", description=f"{member} ({member.id})", color=discord.Color.dark_grey(), timestamp=datetime.now(timezone.utc))
    await log_event(member.guild, embed)


@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    embed = discord.Embed(title="🗑️ Mesaj Silindi", color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Yazan", value=message.author.mention, inline=True)
    embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
    if message.content:
        embed.add_field(name="İçerik", value=message.content[:1000], inline=False)
    await log_event(message.guild, embed)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or not before.guild or before.content == after.content:
        return
    embed = discord.Embed(title="✏️ Mesaj Düzenlendi", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Yazan", value=before.author.mention, inline=True)
    embed.add_field(name="Kanal", value=before.channel.mention, inline=True)
    embed.add_field(name="Önce", value=(before.content or "*(boş)*")[:500], inline=False)
    embed.add_field(name="Sonra", value=(after.content or "*(boş)*")[:500], inline=False)
    await log_event(before.guild, embed)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    member = message.author
    data = get_guild_data(message.guild.id)

    if not is_mod(member):
        # Kilit modu: doğrulanmamış üyelerin mesajlarını sil
        if data.get("lockdown"):
            unverified_role = message.guild.get_role(data["unverified_role_id"]) if data["unverified_role_id"] else None
            if unverified_role and unverified_role in member.roles:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                return

        lowered = message.content.lower()

        # Anti-link
        if "discord.gg/" in lowered or "discord.com/invite/" in lowered:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {member.mention} davet linki paylaşamazsın!", delete_after=5)
            except discord.Forbidden:
                pass
            return

        # Yasaklı kelime filtresi
        if any(word in lowered for word in data.get("banned_words", [])):
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {member.mention} mesajın yasaklı kelime içeriyor!", delete_after=5)
            except discord.Forbidden:
                pass
            return

        # Anti mention-spam
        if len(message.mentions) >= MENTION_SPAM_LIMIT:
            try:
                await message.delete()
                await member.timeout(timedelta(minutes=SPAM_TIMEOUT_MINUTES), reason="Toplu mention spam")
                await message.channel.send(f"🔇 {member.mention} toplu mention attığı için susturuldu.")
            except discord.Forbidden:
                pass
            return

        # Anti-spam (flood)
        now = time.time()
        times = message_times[(message.guild.id, member.id)]
        times.append(now)
        if len(times) == SPAM_MESSAGE_LIMIT and (now - times[0]) <= SPAM_TIME_WINDOW:
            try:
                await member.timeout(timedelta(minutes=SPAM_TIMEOUT_MINUTES), reason="Otomatik anti-spam")
                await message.channel.send(f"🔇 {member.mention} spam yaptığı için {SPAM_TIMEOUT_MINUTES} dakika susturuldu.")
                embed = discord.Embed(
                    title="🛡️ Anti-Spam Tetiklendi",
                    description=f"{member.mention} kısa sürede çok fazla mesaj attığı için susturuldu.",
                    color=discord.Color.red(),
                )
                await log_event(message.guild, embed)
            except discord.Forbidden:
                pass
            times.clear()

    # XP kazanımı (spam durumunda da makul, çünkü cooldown var)
    key = (message.guild.id, member.id)
    now = time.time()
    last = xp_cooldowns.get(key, 0)
    if now - last >= XP_COOLDOWN:
        xp_cooldowns[key] = now
        uid = str(member.id)
        info = data["xp"].setdefault(uid, {"xp": 0, "level": 0})
        eski_seviye = level_for_xp(info["xp"])
        info["xp"] += random.randint(XP_MIN, XP_MAX)
        yeni_seviye = level_for_xp(info["xp"])
        save_guild_data(message.guild.id, data)
        if yeni_seviye > eski_seviye:
            try:
                await message.channel.send(f"🎉 {member.mention} **Seviye {yeni_seviye}**'e yükseldi!")
            except discord.Forbidden:
                pass

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bu komutu kullanmak için yetkin yok.", delete_after=6)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Eksik parametre var. `{PREFIX}yardim` yazarak komut kullanımına bakabilirsin.", delete_after=8)
    elif isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.RoleNotFound, commands.ChannelNotFound)):
        await ctx.send("⚠️ Belirttiğin kullanıcı/rol/kanal bulunamadı. Doğru şekilde etiketlediğinden emin ol.", delete_after=8)
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"❌ Komut hatası: {error}")


# ======================================================================
# BAŞLAT
# ======================================================================
if __name__ == "__main__":
    print("🛡️ YigitScript Security başlatılıyor...")
    bot.run(TOKEN)
