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
# FLASK (Render için Web Sunucusu)
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
# GENEL GÜVENLİK AYARLARI
# ======================================================================
SPAM_MESSAGE_LIMIT = 5
SPAM_TIME_WINDOW = 6
SPAM_TIMEOUT_MINUTES = 5
MENTION_SPAM_LIMIT = 5
RAID_JOIN_LIMIT = 8
RAID_TIME_WINDOW = 15
XP_MIN = 15
XP_MAX = 25
XP_COOLDOWN = 60

DB_FILE = "guvenlik_data.json"

# ======================================================================
# DİL SİSTEMİ - TÜM ÇEVİRİLER
# ======================================================================
LANGUAGES = {
    "tr": {
        "name": "🇹🇷 Türkçe",
        "bot_started": "✅ Bot hazır! {bot_user}",
        "bot_guilds": "📊 {guild_count} sunucuda aktif",
        "help_title": "🛡️ YigitScript Security — Yardım Menüsü",
        "help_description": "Aşağıdaki menüden bir kategori seç.\n\n**Sistemler:** HGBB • Otorol • Moderasyon • Güvenlik • Seviye • Ticket • Çekiliş",
        "help_select_placeholder": "📂 Bir kategori seç...",
        "help_categories": ["ℹ️ Genel", "🚪 HGBB / Otorol", "🛡️ Moderasyon", "🔒 Güvenlik Ayarları", "⭐ Seviye Sistemi", "🎫 Ticket", "🎉 Çekiliş"],
        "help_genel_title": "ℹ️ Genel Komutlar",
        "help_genel_desc": "`{prefix}yardim` — Bu menüyü açar\n`{prefix}bilgi` — Sunucu ve bot hakkında bilgi\n`{prefix}ping` — Bot gecikmesini gösterir\n`{prefix}ayarlar` — Sunucu yapılandırmasını gösterir\n`{prefix}dil` — Bot dilini değiştirir",
        "help_hgbb_title": "🚪 HGBB & Otorol",
        "help_hgbb_desc": "`{prefix}hgbb-ayarla #kanal` *(yetkili)*\n`{prefix}otorol-ayarla @rol` *(yetkili)* — giren herkese otomatik rol verilir\n`{prefix}otorol-kapat` *(yetkili)* — otorolü kapatır",
        "help_mod_title": "🛡️ Moderasyon",
        "help_mod_desc": "`{prefix}at @üye [sebep]` — sunucudan atar\n`{prefix}yasakla @üye [sebep]` — banlar\n`{prefix}yasak-kaldir id` — ban kaldırır\n`{prefix}sustur @üye dakika [sebep]`\n`{prefix}sustur-kaldir @üye`\n`{prefix}uyar @üye [sebep]`\n`{prefix}uyarilar @üye`\n`{prefix}temizle [adet]`\n`{prefix}kilitle` / `{prefix}kilit-ac`\n`{prefix}yavaslat saniye`\n`{prefix}rol-ver @üye @rol` / `{prefix}rol-al @üye @rol`",
        "help_guvenlik_title": "🔒 Güvenlik Ayarları",
        "help_guvenlik_desc": "`{prefix}ayarla-log #kanal`\n`{prefix}mod-rol @rol`\n`{prefix}kufur-engel ac/kapat` *(yetkili)*\n`{prefix}yasakli-ekle kelime`\n`{prefix}yasakli-sil kelime`\n`{prefix}sunucu-kilitle` / `{prefix}sunucu-kilit-ac`\n\n**Otomatik:** anti-spam, anti-raid, anti-link, mention-spam, küfür filtresi.",
        "help_seviye_title": "⭐ Seviye Sistemi",
        "help_seviye_desc": "`{prefix}seviye [@üye]`\n`{prefix}liderlik`\n\nMesaj attıkça XP kazanırsın (60sn cooldown).",
        "help_ticket_title": "🎫 Ticket Sistemi",
        "help_ticket_desc": "`{prefix}ayarla-ticket #kategori` *(yetkili)*\n`{prefix}ticket-kur` *(yetkili)*",
        "help_cekilis_title": "🎉 Çekiliş",
        "help_cekilis_desc": "`{prefix}cekilis dakika ödül` *(yetkili)*",
        "no_permission": "❌ Bu komutu kullanmak için yetkin yok.",
        "hgbb_set": "✅ HGBB kanalı {channel} olarak ayarlandı! Bundan sonra giren-çıkan bildirimleri bu kanala yapılacak.",
        "otorol_set": "✅ Otorol ayarlandı! Sunucuya yeni katılan herkese otomatik olarak {role} rolü verilecek.",
        "otorol_disabled": "✅ Otorol kapatıldı. Artık yeni üyelere otomatik rol verilmeyecek.",
        "welcome_message": "👋 **{member_mention}** sunucuya katıldı! Seninle birlikte **{member_count}** kişi olduk! 🎉\nSunucu kurallarını okumayı unutma!",
        "leave_message": "😢 **{member_name}** sunucudan ayrıldı. Sensiz **{member_count}** kişi kaldık...",
        "language_set": "✅ Bot dili **Türkçe** olarak ayarlandı!",
        "language_select_title": "🌍 Dil Seçimi / Language Selection",
        "language_select_desc": "Lütfen botun dilini seçin:\nPlease select bot language:\n\n🇹🇷 **Türkçe**\n🇬🇧 **English**",
        "kufur_engel_on": "✅ Küfür engelleme sistemi **aktif**! Artık küfürlü mesajlar otomatik silinecek.",
        "kufur_engel_off": "✅ Küfür engelleme sistemi **devre dışı** bırakıldı.",
        "kufur_engel_warning": "⚠️ {member} mesajın küfür içerdiği için silindi!",
        "turkish_badwords": ["sik", "amk", "orospu", "yarrak", "siktir", "ananı", "göt", "piç", "ibne", "amına", "sokayım", "sokim", "aq", "mk", "amcık", "sikik", "sikim", "pezevenk", "kahpe", "fahişe", "orosbu"],
        "english_badwords": ["fuck", "shit", "ass", "bitch", "dick", "pussy", "bastard", "whore", "slut", "motherfucker", "fcker", "fck", "fcking", "fucking", "sh1t", "b1tch"],
    },
    "en": {
        "name": "🇬🇧 English",
        "bot_started": "✅ Bot ready! {bot_user}",
        "bot_guilds": "📊 Active in {guild_count} servers",
        "help_title": "🛡️ YigitScript Security — Help Menu",
        "help_description": "Select a category from the menu below.\n\n**Systems:** Welcome • Autorole • Moderation • Security • Levels • Tickets • Giveaway",
        "help_select_placeholder": "📂 Select a category...",
        "help_categories": ["ℹ️ General", "🚪 Welcome / Autorole", "🛡️ Moderation", "🔒 Security Settings", "⭐ Level System", "🎫 Tickets", "🎉 Giveaway"],
        "help_genel_title": "ℹ️ General Commands",
        "help_genel_desc": "`{prefix}help` — Opens this menu\n`{prefix}info` — Shows server & bot info\n`{prefix}ping` — Shows bot latency\n`{prefix}settings` — Shows server configuration\n`{prefix}language` — Changes bot language",
        "help_hgbb_title": "🚪 Welcome & Autorole",
        "help_hgbb_desc": "`{prefix}welcome-set #channel` *(admin)*\n`{prefix}autorole-set @role` *(admin)* — auto role for new members\n`{prefix}autorole-off` *(admin)* — disables autorole",
        "help_mod_title": "🛡️ Moderation",
        "help_mod_desc": "`{prefix}kick @member [reason]`\n`{prefix}ban @member [reason]`\n`{prefix}unban id`\n`{prefix}mute @member minutes [reason]`\n`{prefix}unmute @member`\n`{prefix}warn @member [reason]`\n`{prefix}warnings @member`\n`{prefix}clear [amount]`\n`{prefix}lock` / `{prefix}unlock`\n`{prefix}slowmode seconds`\n`{prefix}giverole @member @role` / `{prefix}removerole @member @role`",
        "help_guvenlik_title": "🔒 Security Settings",
        "help_guvenlik_desc": "`{prefix}set-log #channel`\n`{prefix}mod-role @role`\n`{prefix}swear-filter on/off` *(admin)*\n`{prefix}add-bannedword word`\n`{prefix}remove-bannedword word`\n`{prefix}server-lock` / `{prefix}server-unlock`\n\n**Auto protection:** anti-spam, anti-raid, anti-link, mention-spam, swear filter.",
        "help_seviye_title": "⭐ Level System",
        "help_seviye_desc": "`{prefix}rank [@member]`\n`{prefix}leaderboard`\n\nEarn XP by chatting (60s cooldown).",
        "help_ticket_title": "🎫 Ticket System",
        "help_ticket_desc": "`{prefix}set-ticket #category` *(admin)*\n`{prefix}ticket-setup` *(admin)*",
        "help_cekilis_title": "🎉 Giveaway",
        "help_cekilis_desc": "`{prefix}giveaway minutes prize` *(admin)*",
        "no_permission": "❌ You don't have permission to use this command.",
        "hgbb_set": "✅ Welcome channel set to {channel}! Join/leave notifications will be sent here.",
        "otorol_set": "✅ Autorole set! All new members will automatically receive {role} role.",
        "otorol_disabled": "✅ Autorole disabled. New members will no longer receive automatic roles.",
        "welcome_message": "👋 **{member_mention}** joined the server! We are now **{member_count}** members! 🎉\nDon't forget to read the rules!",
        "leave_message": "😢 **{member_name}** left the server. We are now **{member_count}** members without you...",
        "language_set": "✅ Bot language set to **English**!",
        "language_select_title": "🌍 Dil Seçimi / Language Selection",
        "language_select_desc": "Lütfen botun dilini seçin:\nPlease select bot language:\n\n🇹🇷 **Türkçe**\n🇬🇧 **English**",
        "kufur_engel_on": "✅ Swear filter **enabled**! Offensive messages will be automatically deleted.",
        "kufur_engel_off": "✅ Swear filter **disabled**.",
        "kufur_engel_warning": "⚠️ {member} your message was deleted for containing offensive language!",
        "english_badwords": ["fuck", "shit", "ass", "bitch", "dick", "pussy", "bastard", "whore", "slut", "motherfucker", "fcker", "fck", "fcking", "fucking", "sh1t", "b1tch", "nigger", "retard", "cunt", "cock"],
        "turkish_badwords": ["sik", "amk", "orospu", "yarrak", "siktir", "ananı", "göt", "piç", "ibne", "amına", "sokayım", "sokim", "aq", "mk", "amcık", "sikik", "sikim", "pezevenk", "kahpe", "fahişe", "orosbu"],
    }
}


def get_lang(guild_id):
    data = get_guild_data(guild_id)
    lang = data.get("language", "tr")
    return LANGUAGES.get(lang, LANGUAGES["tr"])


def get_text(guild_id, key, **kwargs):
    lang = get_lang(guild_id)
    text = lang.get(key, LANGUAGES["tr"].get(key, key))
    return text.format(**kwargs)


# ======================================================================
# VERİTABANI
# ======================================================================
def _default_guild_data():
    return {
        "language": "tr",
        "welcome_channel_id": None,
        "log_channel_id": None,
        "mod_role_id": None,
        "ticket_category_id": None,
        "ticket_counter": 0,
        "banned_words": [],
        "lockdown": False,
        "warns": {},
        "xp": {},
        "otorol_role_id": None,
        "kufur_engel": True,
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
xp_cooldowns = {}
bot_start_time = time.time()

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
        lang = get_lang(ctx.guild.id)
        await ctx.send(lang["no_permission"], delete_after=6)
        return False
    return commands.check(predicate)


def level_for_xp(xp: int) -> int:
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


def get_badwords(guild_id):
    data = get_guild_data(guild_id)
    lang_code = data.get("language", "tr")
    lang = LANGUAGES.get(lang_code, LANGUAGES["tr"])
    return lang.get(f"{lang_code}_badwords", []) + lang.get("english_badwords", [])


# ======================================================================
# DİL SEÇİM MENÜSÜ
# ======================================================================
class LanguageSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🇹🇷 Türkçe", value="tr", description="Bot dilini Türkçe yap"),
            discord.SelectOption(label="🇬🇧 English", value="en", description="Set bot language to English"),
        ]
        super().__init__(placeholder="Dil seçin / Select language...", options=options, custom_id="ys_lang_select")

    async def callback(self, interaction: discord.Interaction):
        data = get_guild_data(interaction.guild.id)
        data["language"] = self.values[0]
        save_guild_data(interaction.guild.id, data)
        lang = get_lang(interaction.guild.id)
        await interaction.response.edit_message(content=lang["language_set"], embed=None, view=None)


class LanguageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(LanguageSelect())


# ======================================================================
# TICKET SİSTEMİ
# ======================================================================
class TicketOpenView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="🎫", style=discord.ButtonStyle.primary, custom_id="ys_ticket_open_main")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        data = get_guild_data(guild.id)
        lang = get_lang(guild.id)
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
                reason=f"{interaction.user} opened ticket",
            )
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Cannot create ticket channel. Check my permissions.", ephemeral=True)
            return

        if data["language"] == "tr":
            title = f"🎫 Destek Talebi #{ticket_no:04d}"
            desc = f"{interaction.user.mention}, talebini buradan yaz. Yetkili en kısa sürede yardımcı olacak."
        else:
            title = f"🎫 Support Ticket #{ticket_no:04d}"
            desc = f"{interaction.user.mention}, write your request here. Staff will help soon."

        embed = discord.Embed(title=title, description=desc, color=discord.Color.blurple())
        await channel.send(embed=embed, view=TicketCloseView(lang))
        await interaction.response.send_message(f"✅ {channel.mention}", ephemeral=True)


class TicketCloseView(discord.ui.View):
    def __init__(self, lang):
        super().__init__(timeout=None)
        self.lang = lang
        label = "🔒 Talebi Kapat" if lang == LANGUAGES["tr"] else "🔒 Close Ticket"
        self.close_button = discord.ui.Button(label=label, style=discord.ButtonStyle.danger, custom_id="ys_ticket_close_main")
        self.close_button.callback = self.close_callback
        self.add_item(self.close_button)

    async def close_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔒 Kapatılıyor... / Closing..." if self.lang == LANGUAGES["tr"] else "🔒 Closing...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Closed by {interaction.user}")
        except discord.Forbidden:
            pass


# ======================================================================
# YARDIM MENÜSÜ
# ======================================================================
class HelpSelect(discord.ui.Select):
    def __init__(self, guild_id):
        self.guild_id = guild_id
        lang = get_lang(guild_id)
        categories = lang["help_categories"]
        options = []
        values = ["genel", "hgbb", "mod", "guvenlik", "seviye", "ticket", "cekilis"]
        for i, (cat, val) in enumerate(zip(categories, values)):
            options.append(discord.SelectOption(label=cat, value=val))
        super().__init__(placeholder=lang["help_select_placeholder"], options=options, custom_id=f"ys_help_select_{guild_id}")

    async def callback(self, interaction: discord.Interaction):
        lang = get_lang(self.guild_id)
        pages = {
            "genel": discord.Embed(title=lang["help_genel_title"], description=lang["help_genel_desc"].format(prefix=PREFIX), color=discord.Color.blurple()),
            "hgbb": discord.Embed(title=lang["help_hgbb_title"], description=lang["help_hgbb_desc"].format(prefix=PREFIX), color=discord.Color.green()),
            "mod": discord.Embed(title=lang["help_mod_title"], description=lang["help_mod_desc"].format(prefix=PREFIX), color=discord.Color.red()),
            "guvenlik": discord.Embed(title=lang["help_guvenlik_title"], description=lang["help_guvenlik_desc"].format(prefix=PREFIX), color=discord.Color.orange()),
            "seviye": discord.Embed(title=lang["help_seviye_title"], description=lang["help_seviye_desc"].format(prefix=PREFIX), color=discord.Color.gold()),
            "ticket": discord.Embed(title=lang["help_ticket_title"], description=lang["help_ticket_desc"].format(prefix=PREFIX), color=discord.Color.teal()),
            "cekilis": discord.Embed(title=lang["help_cekilis_title"], description=lang["help_cekilis_desc"].format(prefix=PREFIX), color=discord.Color.magenta()),
        }
        await interaction.response.edit_message(embed=pages[self.values[0]], view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=120)
        self.add_item(HelpSelect(guild_id))


# ======================================================================
# KOMUTLAR - YARDIM
# ======================================================================
@bot.command(name="yardim", aliases=["help"])
async def yardim(ctx):
    lang = get_lang(ctx.guild.id)
    embed = discord.Embed(
        title=lang["help_title"],
        description=lang["help_description"],
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"Prefix: {PREFIX}  |  YigitScript Security")
    await ctx.send(embed=embed, view=HelpView(ctx.guild.id))


@bot.command(name="dil", aliases=["language"])
@mod_only()
async def dil_cmd(ctx):
    data = get_guild_data(ctx.guild.id)
    current_lang = get_lang(ctx.guild.id)
    view = LanguageView()
    await ctx.send(current_lang["language_select_desc"], view=view)


# ======================================================================
# HGBB - SADECE KANAL AYARI
# ======================================================================
@bot.command(name="hgbb-ayarla", aliases=["welcome-set"])
@commands.has_permissions(administrator=True)
async def hgbb_ayarla(ctx, kanal: discord.TextChannel):
    data = get_guild_data(ctx.guild.id)
    data["welcome_channel_id"] = kanal.id
    save_guild_data(ctx.guild.id, data)
    lang = get_lang(ctx.guild.id)
    await ctx.send(lang["hgbb_set"].format(channel=kanal.mention))


# ======================================================================
# OTOROL - BASİT VE OTOMATİK
# ======================================================================
@bot.command(name="otorol-ayarla", aliases=["autorole-set"])
@commands.has_permissions(administrator=True)
async def otorol_ayarla(ctx, rol: discord.Role):
    data = get_guild_data(ctx.guild.id)
    data["otorol_role_id"] = rol.id
    save_guild_data(ctx.guild.id, data)
    lang = get_lang(ctx.guild.id)
    await ctx.send(lang["otorol_set"].format(role=rol.mention))


@bot.command(name="otorol-kapat", aliases=["autorole-off"])
@commands.has_permissions(administrator=True)
async def otorol_kapat(ctx):
    data = get_guild_data(ctx.guild.id)
    data["otorol_role_id"] = None
    save_guild_data(ctx.guild.id, data)
    lang = get_lang(ctx.guild.id)
    await ctx.send(lang["otorol_disabled"])


# ======================================================================
# KÜFÜR ENGEL
# ======================================================================
@bot.command(name="kufur-engel", aliases=["swear-filter"])
@mod_only()
async def kufur_engel(ctx, durum: str):
    data = get_guild_data(ctx.guild.id)
    lang = get_lang(ctx.guild.id)
    if durum.lower() in ["ac", "on", "aktif", "enable"]:
        data["kufur_engel"] = True
        save_guild_data(ctx.guild.id, data)
        await ctx.send(lang["kufur_engel_on"])
    elif durum.lower() in ["kapat", "off", "devredisi", "disable"]:
        data["kufur_engel"] = False
        save_guild_data(ctx.guild.id, data)
        await ctx.send(lang["kufur_engel_off"])
    else:
        await ctx.send("⚠️ Kullanım: `ys!kufur-engel ac/kapat` veya `ys!swear-filter on/off`")


# ======================================================================
# AYARLAR
# ======================================================================
@bot.command(name="ayarlar", aliases=["settings"])
@mod_only()
async def ayarlar(ctx):
    data = get_guild_data(ctx.guild.id)
    g = ctx.guild
    lang = get_lang(ctx.guild.id)

    def fmt_channel(cid):
        ch = g.get_channel(cid) if cid else None
        return ch.mention if ch else "Ayarlanmadı" if data["language"] == "tr" else "Not set"

    def fmt_role(rid):
        role = g.get_role(rid) if rid else None
        return role.mention if role else "Ayarlanmadı" if data["language"] == "tr" else "Not set"

    embed = discord.Embed(title="⚙️ Sunucu Ayarları" if data["language"] == "tr" else "⚙️ Server Settings", color=discord.Color.blurple())
    embed.add_field(name="🌐 Dil / Language", value="🇹🇷 Türkçe" if data["language"] == "tr" else "🇬🇧 English", inline=True)
    embed.add_field(name="📢 HGBB / Welcome", value=fmt_channel(data["welcome_channel_id"]), inline=True)
    embed.add_field(name="📋 Log", value=fmt_channel(data["log_channel_id"]), inline=True)
    embed.add_field(name="🛡️ Yetkili Rolü / Mod Role", value=fmt_role(data["mod_role_id"]), inline=True)
    embed.add_field(name="🎭 Otorol / Autorole", value=fmt_role(data["otorol_role_id"]), inline=True)
    embed.add_field(name="🔒 Kilit / Lockdown", value="🔒 Açık" if data["lockdown"] else "🔓 Kapalı" if data["language"] == "tr" else ("🔒 On" if data["lockdown"] else "🔓 Off"), inline=True)
    embed.add_field(name="🚫 Küfür Engel / Swear Filter", value="✅ Açık" if data["kufur_engel"] else "❌ Kapalı" if data["language"] == "tr" else ("✅ On" if data["kufur_engel"] else "❌ Off"), inline=True)
    embed.add_field(name="📝 Yasaklı Kelime / Banned Words", value=str(len(data["banned_words"])), inline=True)
    await ctx.send(embed=embed)


# ======================================================================
# DİĞER KURULUM KOMUTLARI
# ======================================================================
@bot.command(name="ayarla-log", aliases=["set-log"])
@commands.has_permissions(administrator=True)
async def ayarla_log(ctx, kanal: discord.TextChannel):
    data = get_guild_data(ctx.guild.id)
    data["log_channel_id"] = kanal.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Log kanalı {kanal.mention} olarak ayarlandı.")


@bot.command(name="mod-rol", aliases=["mod-role"])
@commands.has_permissions(administrator=True)
async def mod_rol(ctx, rol: discord.Role):
    data = get_guild_data(ctx.guild.id)
    data["mod_role_id"] = rol.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Yetkili rolü {rol.mention} olarak ayarlandı.")


@bot.command(name="yasakli-ekle", aliases=["add-bannedword"])
@mod_only()
async def yasakli_ekle(ctx, *, kelime: str):
    data = get_guild_data(ctx.guild.id)
    kelime = kelime.lower().strip()
    if kelime not in data["banned_words"]:
        data["banned_words"].append(kelime)
        save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ `{kelime}` yasaklı kelime listesine eklendi.")


@bot.command(name="yasakli-sil", aliases=["remove-bannedword"])
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


@bot.command(name="ayarla-ticket", aliases=["set-ticket"])
@commands.has_permissions(administrator=True)
async def ayarla_ticket(ctx, kategori: discord.CategoryChannel):
    data = get_guild_data(ctx.guild.id)
    data["ticket_category_id"] = kategori.id
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Ticket kategorisi **{kategori.name}** olarak ayarlandı.")


@bot.command(name="ticket-kur", aliases=["ticket-setup"])
@mod_only()
async def ticket_kur(ctx):
    data = get_guild_data(ctx.guild.id)
    if not data["ticket_category_id"]:
        if data["language"] == "tr":
            await ctx.send(f"⚠️ Önce `{PREFIX}ayarla-ticket #kategori` ile ticket kategorisini ayarlayın.")
        else:
            await ctx.send(f"⚠️ Set ticket category first with `{PREFIX}set-ticket #category`.")
        return
    lang = get_lang(ctx.guild.id)
    if data["language"] == "tr":
        title = "🎫 Destek Sistemi"
        desc = "Destek talebi oluşturmak için butona tıkla."
    else:
        title = "🎫 Support System"
        desc = "Click the button to create a support ticket."
    embed = discord.Embed(title=title, description=desc, color=discord.Color.teal())
    await ctx.send(embed=embed, view=TicketOpenView(ctx.guild.id))


@bot.command(name="bilgi", aliases=["info"])
async def bilgi(ctx):
    data = get_guild_data(ctx.guild.id)
    lang = get_lang(ctx.guild.id)
    embed = discord.Embed(title=f"📊 {ctx.guild.name}", color=discord.Color.blurple(), timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👥 Üye Sayısı" if data["language"] == "tr" else "👥 Members", value=str(ctx.guild.member_count), inline=True)
    embed.add_field(name="📡 Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="🔒 Kilit" if data["language"] == "tr" else "🔒 Lockdown", value="Açık" if data["lockdown"] else "Kapalı" if data["language"] == "tr" else ("On" if data["lockdown"] else "Off"), inline=True)
    embed.set_footer(text="YigitScript Security")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")


# ======================================================================
# MODERASYON KOMUTLARI
# ======================================================================
@bot.command(name="at", aliases=["kick"])
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


@bot.command(name="yasakla", aliases=["ban"])
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


@bot.command(name="yasak-kaldir", aliases=["unban"])
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


@bot.command(name="sustur", aliases=["mute"])
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


@bot.command(name="sustur-kaldir", aliases=["unmute"])
@mod_only()
async def remove_timeout_cmd(ctx, kullanici: discord.Member):
    try:
        await kullanici.timeout(None, reason=f"{ctx.author} tarafından kaldırıldı")
    except discord.Forbidden:
        await ctx.send("⚠️ Susturmayı kaldıramıyorum.")
        return
    await ctx.send(f"🔊 {kullanici.mention} kullanıcısının susturması kaldırıldı.")


@bot.command(name="uyar", aliases=["warn"])
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


@bot.command(name="uyarilar", aliases=["warnings"])
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


@bot.command(name="temizle", aliases=["clear"])
@mod_only()
async def clear_cmd(ctx, adet: int = 10):
    adet = max(1, min(adet, 100))
    deleted = await ctx.channel.purge(limit=adet + 1)
    msg = await ctx.send(f"🗑️ {len(deleted) - 1} mesaj silindi.")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except discord.NotFound:
        pass


@bot.command(name="kilitle", aliases=["lock"])
@mod_only()
async def lock_channel(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Bu kanal kilitlendi.")


@bot.command(name="kilit-ac", aliases=["unlock"])
@mod_only()
async def unlock_channel(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send("🔓 Bu kanalın kilidi açıldı.")


@bot.command(name="yavaslat", aliases=["slowmode"])
@mod_only()
async def slowmode_cmd(ctx, saniye: int):
    saniye = max(0, min(saniye, 21600))
    await ctx.channel.edit(slowmode_delay=saniye)
    if saniye == 0:
        await ctx.send("✅ Yavaş mod kapatıldı.")
    else:
        await ctx.send(f"🐢 Yavaş mod {saniye} saniye olarak ayarlandı.")


@bot.command(name="rol-ver", aliases=["giverole"])
@mod_only()
async def give_role_cmd(ctx, kullanici: discord.Member, rol: discord.Role):
    try:
        await kullanici.add_roles(rol, reason=f"{ctx.author} tarafından verildi")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu rolü veremiyorum.")
        return
    await ctx.send(f"✅ {kullanici.mention} kullanıcısına {rol.mention} rolü verildi.")


@bot.command(name="rol-al", aliases=["removerole"])
@mod_only()
async def remove_role_cmd(ctx, kullanici: discord.Member, rol: discord.Role):
    try:
        await kullanici.remove_roles(rol, reason=f"{ctx.author} tarafından alındı")
    except discord.Forbidden:
        await ctx.send("⚠️ Bu rolü alamıyorum.")
        return
    await ctx.send(f"✅ {kullanici.mention} kullanıcısından {rol.mention} rolü alındı.")


@bot.command(name="sunucu-kilitle", aliases=["server-lock"])
@commands.has_permissions(administrator=True)
async def guild_lockdown_on(ctx):
    data = get_guild_data(ctx.guild.id)
    data["lockdown"] = True
    save_guild_data(ctx.guild.id, data)
    await ctx.send("🔒 Sunucu kilit moduna alındı.")


@bot.command(name="sunucu-kilit-ac", aliases=["server-unlock"])
@commands.has_permissions(administrator=True)
async def guild_lockdown_off(ctx):
    data = get_guild_data(ctx.guild.id)
    data["lockdown"] = False
    save_guild_data(ctx.guild.id, data)
    await ctx.send("🔓 Kilit modu kapatıldı.")


# ======================================================================
# SEVİYE SİSTEMİ
# ======================================================================
@bot.command(name="seviye", aliases=["rank"])
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


@bot.command(name="liderlik", aliases=["leaderboard"])
async def leaderboard_cmd(ctx):
    data = get_guild_data(ctx.guild.id)
    siralanmis = sorted(data["xp"].items(), key=lambda kv: kv[1]["xp"], reverse=True)[:10]
    if not siralanmis:
        await ctx.send("Henüz kimse XP kazanmamış." if data["language"] == "tr" else "No one has earned XP yet.")
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
# ÇEKİLİŞ
# ======================================================================
@bot.command(name="cekilis", aliases=["giveaway"])
@mod_only()
async def giveaway_cmd(ctx, dakika: int, *, odul: str):
    lang = get_lang(ctx.guild.id)
    bitis = datetime.now(timezone.utc) + timedelta(minutes=dakika)
    if lang == LANGUAGES["tr"]:
        title = "🎉 ÇEKİLİŞ BAŞLADI!"
        desc = f"**Ödül:** {odul}\n\nKatılmak için 🎉 ile tepki ver!\n**Bitiş:** {dakika} dakika sonra"
        footer = f"Başlatan: {ctx.author}"
    else:
        title = "🎉 GIVEAWAY STARTED!"
        desc = f"**Prize:** {odul}\n\nReact with 🎉 to enter!\n**Ends in:** {dakika} minutes"
        footer = f"Started by: {ctx.author}"
    embed = discord.Embed(title=title, description=desc, color=discord.Color.magenta())
    embed.set_footer(text=footer)
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
        if lang == LANGUAGES["tr"]:
            await ctx.send(f"🎉 Çekiliş sona erdi ama kimse katılmamış! Ödül: **{odul}**")
        else:
            await ctx.send(f"🎉 Giveaway ended but no one joined! Prize: **{odul}**")
        return

    kazanan = random.choice(katilimcilar)
    if lang == LANGUAGES["tr"]:
        sonuc_title = "🎉 ÇEKİLİŞ SONA ERDİ!"
        sonuc_desc = f"**Ödül:** {odul}\n**Kazanan:** {kazanan.mention}\n\nTebrikler! 🎊"
    else:
        sonuc_title = "🎉 GIVEAWAY ENDED!"
        sonuc_desc = f"**Prize:** {odul}\n**Winner:** {kazanan.mention}\n\nCongratulations! 🎊"
    sonuc_embed = discord.Embed(title=sonuc_title, description=sonuc_desc, color=discord.Color.green())
    await ctx.send(embed=sonuc_embed)


# ======================================================================
# ÖZEL KANAL MESAJI (1531992520547106930)
# ======================================================================
TARGET_CHANNEL_ID = 1531992520547106930


@tasks.loop(minutes=5)
async def send_status_message():
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        try:
            channel = await bot.fetch_channel(TARGET_CHANNEL_ID)
        except:
            return
    if not channel:
        return

    uptime_seconds = int(time.time() - bot_start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    uptime_str = f"{hours}:{minutes:02d}:{seconds:02d}"

    ping = round(bot.latency * 1000)
    guild_count = len(bot.guilds)
    total_members = sum(g.member_count for g in bot.guilds)
    total_xp = 0
    db = load_db()
    for gid, gdata in db.get("guilds", {}).items():
        for uid, xpdata in gdata.get("xp", {}).items():
            total_xp += xpdata.get("xp", 0)

    embed = discord.Embed(
        title="🛡️ **YIGITSCRIPT SECURITY** 🛡️",
        description="```ansi\n⚡ YIGIT SECURITY — ONLINE & READY\n```",
        color=0x00ff00,
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(
        name="📊 **SUNUCU BİLGİLERİ**",
        value=f"```\n"
              f"┌ 👥 Sunucu Sayısı: {guild_count}\n"
              f"├ 👤 Toplam Üye: {total_members:,}\n"
              f"├ 🛡️ Korunan Üye: {total_members:,}\n"
              f"└ ⭐ Toplam XP: {total_xp:,}\n"
              f"```",
        inline=False
    )

    embed.add_field(
        name="💻 **SİSTEM DURUMU**",
        value=f"```\n"
              f"┌ 📡 Ping: {ping}ms\n"
              f"├ ⏱️ Uptime: {uptime_str}\n"
              f"├ 🔒 Anti-Spam: ✅ Aktif\n"
              f"├ 🚫 Küfür Filtresi: ✅ Aktif\n"
              f"├ 🔗 Anti-Link: ✅ Aktif\n"
              f"└ 🛡️ Anti-Raid: ✅ Aktif\n"
              f"```",
        inline=False
    )

    embed.add_field(
        name="🛡️ **GÜVENLİK ÖZELLİKLERİ**",
        value=f"```\n"
              f"┌ 🔇 Anti-Spam (Flood)\n"
              f"├ 📢 Anti-Mention Spam\n"
              f"├ 🔗 Anti-Discord Link\n"
              f"├ 🚫 Küfür Engelleme\n"
              f"├ 🌍 Çoklu Dil Desteği (TR/EN)\n"
              f"├ 🚪 HGBB Sistemi\n"
              f"├ 🎭 Otomatik Rol\n"
              f"├ ⚠️ Uyarı Sistemi (3 uyarı = otomatik mute)\n"
              f"├ 🔒 Sunucu Kilitleme\n"
              f"└ 🚨 Anti-Raid Koruması\n"
              f"```",
        inline=False
    )

    embed.add_field(
        name="🔗 **KOMUTLAR**",
        value=f"`{PREFIX}yardim` • `{PREFIX}help` • `{PREFIX}dil` • `{PREFIX}ayarlar`\n"
              f"`{PREFIX}hgbb-ayarla` • `{PREFIX}otorol-ayarla`\n"
              f"`{PREFIX}kufur-engel` • `{PREFIX}sunucu-kilitle`",
        inline=False
    )

    embed.set_footer(text="YigitScript Security • 7/24 Koruma • ys!yardim")
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)

    # Önceki mesajları silip yenisini gönder
    try:
        async for msg in channel.history(limit=5):
            if msg.author == bot.user:
                try:
                    await msg.delete()
                except:
                    pass
        await channel.send(embed=embed)
    except discord.Forbidden:
        pass
    except Exception as e:
        print(f"Status message error: {e}")


# ======================================================================
# ROTATING STATUS
# ======================================================================
STATUS_MESSAGES = [
    ("watching", "YigitScript Security 🛡️"),
    ("listening", f"{PREFIX}yardim"),
    ("watching", "sunucunu koruyorum 🛡️"),
    ("competing", "anti-raid & anti-spam"),
    ("watching", "over your server 👀"),
    ("listening", f"{PREFIX}help"),
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

    # Kalıcı view'ları ekle
    bot.add_view(TicketOpenView(0))  # placeholder, her sunucu için ayrı
    bot.add_view(TicketCloseView(LANGUAGES["tr"]))
    bot.add_view(TicketCloseView(LANGUAGES["en"]))

    if not status_loop.is_running():
        status_loop.start()
    if not send_status_message.is_running():
        send_status_message.start()


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    data = get_guild_data(guild.id)
    lang = get_lang(guild.id)
    now = time.time()
    joins = join_times_by_guild[guild.id]
    joins.append(now)

    # Anti-raid kontrolü
    if len(joins) == RAID_JOIN_LIMIT and (now - joins[0]) <= RAID_TIME_WINDOW and not data["lockdown"]:
        data["lockdown"] = True
        save_guild_data(guild.id, data)
        embed = discord.Embed(
            title="🚨 RAID DETECTED!" if lang != LANGUAGES["tr"] else "🚨 OLASI RAID TESPİT EDİLDİ",
            description=f"{RAID_JOIN_LIMIT} members joined in {RAID_TIME_WINDOW}s. Server locked." if lang != LANGUAGES["tr"] else f"Son {RAID_TIME_WINDOW} saniyede {RAID_JOIN_LIMIT} üye katıldı. Sunucu otomatik kilitlendi.",
            color=discord.Color.dark_red(),
        )
        await log_event(guild, embed)

    # Otorol
    otorol_role_id = data.get("otorol_role_id")
    if otorol_role_id:
        otorol_role = guild.get_role(otorol_role_id)
        if otorol_role:
            try:
                await member.add_roles(otorol_role, reason="Otomatik rol (otorol)")
            except discord.Forbidden:
                pass

    # HGBB mesajı
    welcome_channel = guild.get_channel(data["welcome_channel_id"]) if data["welcome_channel_id"] else None
    if welcome_channel:
        welcome_msg = lang["welcome_message"].format(
            member_mention=member.mention,
            member_name=member.display_name,
            member_count=guild.member_count
        )
        embed = discord.Embed(
            description=welcome_msg,
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await welcome_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # Log
    log_embed = discord.Embed(
        title="📥 Member Joined" if lang != LANGUAGES["tr"] else "📥 Üye Katıldı",
        description=f"{member.mention} ({member.id})",
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    )
    await log_event(guild, log_embed)


@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    data = get_guild_data(guild.id)
    lang = get_lang(guild.id)

    # HGBB çıkış mesajı
    welcome_channel = guild.get_channel(data["welcome_channel_id"]) if data["welcome_channel_id"] else None
    if welcome_channel:
        leave_msg = lang["leave_message"].format(
            member_mention=member.mention,
            member_name=member.display_name,
            member_count=guild.member_count
        )
        embed = discord.Embed(
            description=leave_msg,
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await welcome_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # Log
    log_embed = discord.Embed(
        title="📤 Member Left" if lang != LANGUAGES["tr"] else "📤 Üye Ayrıldı",
        description=f"{member} ({member.id})",
        color=discord.Color.dark_grey(),
        timestamp=datetime.now(timezone.utc)
    )
    await log_event(guild, log_embed)


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
    lang = get_lang(message.guild.id)

    if not is_mod(member):
        lowered = message.content.lower()

        # Kilit modu - herkesin mesajını engelle
        if data.get("lockdown"):
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            return

        # Küfür filtresi
        if data.get("kufur_engel", True):
            badwords = get_badwords(message.guild.id)
            for word in badwords:
                if word in lowered:
                    try:
                        await message.delete()
                        warning = await message.channel.send(
                            lang["kufur_engel_warning"].format(member=member.mention),
                            delete_after=5
                        )
                    except discord.Forbidden:
                        pass
                    return

        # Anti-link
        if "discord.gg/" in lowered or "discord.com/invite/" in lowered:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {member.mention} davet linki paylaşamazsın!" if lang == LANGUAGES["tr"] else f"⚠️ {member.mention} you cannot share invite links!", delete_after=5)
            except discord.Forbidden:
                pass
            return

        # Yasaklı kelime filtresi
        if any(word in lowered for word in data.get("banned_words", [])):
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {member.mention} mesajın yasaklı kelime içeriyor!" if lang == LANGUAGES["tr"] else f"⚠️ {member.mention} your message contains a banned word!", delete_after=5)
            except discord.Forbidden:
                pass
            return

        # Anti mention-spam
        if len(message.mentions) >= MENTION_SPAM_LIMIT:
            try:
                await message.delete()
                await member.timeout(timedelta(minutes=SPAM_TIMEOUT_MINUTES), reason="Toplu mention spam")
                await message.channel.send(f"🔇 {member.mention} toplu mention attığı için susturuldu." if lang == LANGUAGES["tr"] else f"🔇 {member.mention} muted for mass mention spam.")
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
                await message.channel.send(f"🔇 {member.mention} spam yaptığı için {SPAM_TIMEOUT_MINUTES} dakika susturuldu." if lang == LANGUAGES["tr"] else f"🔇 {member.mention} muted for {SPAM_TIMEOUT_MINUTES} minutes for spamming.")
                embed = discord.Embed(
                    title="🛡️ Anti-Spam" if lang == LANGUAGES["tr"] else "🛡️ Anti-Spam Triggered",
                    description=f"{member.mention} kısa sürede çok fazla mesaj attığı için susturuldu." if lang == LANGUAGES["tr"] else f"{member.mention} muted for sending too many messages.",
                    color=discord.Color.red(),
                )
                await log_event(message.guild, embed)
            except discord.Forbidden:
                pass
            times.clear()

    # XP kazanımı
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
                await message.channel.send(f"🎉 {member.mention} **Seviye {yeni_seviye}**'e yükseldi!" if lang == LANGUAGES["tr"] else f"🎉 {member.mention} leveled up to **Level {yeni_seviye}**!")
            except discord.Forbidden:
                pass

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(get_text(ctx.guild.id if ctx.guild else None, "no_permission"), delete_after=6)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Eksik parametre var. `{PREFIX}yardim` yazarak komut kullanımına bakabilirsin.", delete_after=8)
    elif isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.RoleNotFound, commands.ChannelNotFound)):
        await ctx.send("⚠️ Belirttiğin kullanıcı/rol/kanal bulunamadı.", delete_after=8)
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
