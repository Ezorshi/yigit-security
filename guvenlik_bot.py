"""
====================================================================
  YIGIT GÜVENLİK BOTU (Render Uyumlu)
====================================================================
"""

import discord
from discord.ext import commands
import json
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from flask import Flask
import threading

# ======================================================================
# WEB SUNUCUSU (Render için)
# ======================================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Yigit Güvenlik Botu çalışıyor!"

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

# ======================================================================
# AYARLAR (Kendi ID'lerinle doldur!)
# ======================================================================
UNVERIFIED_ROLE_ID = 0  # Doğrulanmamış rolü
VERIFIED_ROLE_ID = 0    # Üye rolü
WELCOME_CHANNEL_ID = 0  # Hoş geldin kanalı
LOG_CHANNEL_ID = 0      # Log kanalı
MOD_ROLE_ID = 0         # Yetkili rolü

# Otorol - Kendi kendine rol seçme
SELF_ROLES = {
    "🎮": (0, "Oyuncu"),
    "🎨": (0, "Tasarım"),
    "📢": (0, "Duyuru"),
}

# Güvenlik ayarları
SPAM_MESSAGE_LIMIT = 5
SPAM_TIME_WINDOW = 6
SPAM_TIMEOUT_MINUTES = 5
RAID_JOIN_LIMIT = 8
RAID_TIME_WINDOW = 15
BANNED_WORDS = {"küfür1", "küfür2", "hakaret"}

# ======================================================================
# VERİTABANI
# ======================================================================
DB_FILE = "guvenlik_data.json"

def load_db():
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"verified_users": [], "warns": {}, "lockdown": False}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

# ======================================================================
# BOT
# ======================================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

message_times = defaultdict(lambda: deque(maxlen=SPAM_MESSAGE_LIMIT))
join_times = deque(maxlen=RAID_JOIN_LIMIT)

# ======================================================================
# HGBB BUTONU
# ======================================================================
class HGBBVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Doğrula ve Sunucuya Katıl", style=discord.ButtonStyle.success, custom_id="hgbb_verify")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        guild = interaction.guild

        verified_role = guild.get_role(VERIFIED_ROLE_ID)
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)

        if not verified_role:
            await interaction.response.send_message("⚠️ Üye rolü ayarlanmamış!", ephemeral=True)
            return

        if verified_role in member.roles:
            await interaction.response.send_message("Zaten doğrulanmışsın! 🎉", ephemeral=True)
            return

        try:
            await member.add_roles(verified_role, reason="HGBB doğrulaması")
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role, reason="HGBB doğrulaması tamamlandı")
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Rol verme yetkim yok!", ephemeral=True)
            return

        db = load_db()
        if member.id not in db["verified_users"]:
            db["verified_users"].append(member.id)
            save_db(db)

        await interaction.response.send_message("✅ Doğrulandın, sunucuya hoş geldin!", ephemeral=True)

# ======================================================================
# OTOROL BUTONU
# ======================================================================
class SelfRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for emoji, (role_id, name) in SELF_ROLES.items():
            if role_id:
                self.add_item(SelfRoleButton(emoji, role_id, name))

class SelfRoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id, name):
        super().__init__(label=name, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f"otorol_{role_id}")
        self.role_id = role_id
        self.role_name = name

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("⚠️ Bu rol artık mevcut değil.", ephemeral=True)
            return
        if role in member.roles:
            await member.remove_roles(role, reason="Otorol - kaldırıldı")
            await interaction.response.send_message(f"➖ **{self.role_name}** rolü kaldırıldı.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Otorol - eklendi")
            await interaction.response.send_message(f"➕ **{self.role_name}** rolü verildi.", ephemeral=True)

# ======================================================================
# KOMUTLAR
# ======================================================================
@bot.command(name='hgbb-kur')
@commands.has_permissions(administrator=True)
async def hgbb_kur(ctx):
    embed = discord.Embed(
        title="🚪 Sunucuya Hoş Geldin!",
        description=(
            "Sunucunun tüm kanallarını görebilmek için aşağıdaki butona basarak "
            "kendini doğrulaman gerekiyor.\n\n"
            "Butona bastığında otomatik olarak üye rolün verilecek."
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Yigit Güvenlik Botu | HGBB")
    await ctx.send(embed=embed, view=HGBBVerifyView())
    await ctx.send("✅ Doğrulama mesajı bu kanala kuruldu.")

@bot.command(name='otorol-kur')
@commands.has_permissions(administrator=True)
async def otorol_kur(ctx):
    aciklama = "\n".join(f"{emoji} — **{name}**" for emoji, (rid, name) in SELF_ROLES.items() if rid)
    if not aciklama:
        aciklama = "⚠️ Henüz hiç rol ayarlanmamış!"
    
    embed = discord.Embed(
        title="🎭 Rol Seçimi",
        description=f"İlgilendiğin rolleri seçmek için aşağıdaki butonlara tıkla:\n\n{aciklama}",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed, view=SelfRoleView())
    await ctx.send("✅ Otorol menüsü bu kanala kuruldu.")

@bot.command(name='yardim')
async def yardim(ctx):
    embed = discord.Embed(
        title="🛡️ YIGIT GÜVENLİK BOTU",
        description="**Komutlar:**\n"
                    "`!hgbb-kur` — HGBB doğrulama mesajını kurar (Admin)\n"
                    "`!otorol-kur` — Otorol menüsünü kurar (Admin)\n"
                    "`!yardim` — Bu menüyü gösterir\n\n"
                    "**Sistemler:**\n"
                    "• HGBB - Giriş Onay Sistemi\n"
                    "• Otorol - Kendi kendine rol seçme\n"
                    "• Anti-spam - Flood koruması\n"
                    "• Anti-raid - Çoklu giriş koruması\n"
                    "• Anti-link - Davet linki filtresi\n"
                    "• Yasaklı kelime filtresi\n"
                    "• Loglama - Tüm olaylar loglanır",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Yigit Güvenlik Botu")
    await ctx.send(embed=embed)

# ======================================================================
# OLAYLAR
# ======================================================================
@bot.event
async def on_ready():
    print(f'✅ Bot hazir! {bot.user}')
    print(f'📊 {len(bot.guilds)} sunucuda aktif')
    
    bot.add_view(HGBBVerifyView())
    bot.add_view(SelfRoleView())

@bot.event
async def on_member_join(member):
    guild = member.guild
    now = time.time()
    join_times.append(now)
    
    if len(join_times) == RAID_JOIN_LIMIT and (now - join_times[0]) <= RAID_TIME_WINDOW:
        db = load_db()
        if not db.get("lockdown"):
            db["lockdown"] = True
            save_db(db)
            channel = guild.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send("🚨 **RAID TESPİT EDİLDİ!** Sunucu otomatik kilitlendi.")
    
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
    if unverified_role:
        try:
            await member.add_roles(unverified_role, reason="HGBB - yeni üye")
        except:
            pass
    
    channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="👋 Aramıza Hoş Geldin!",
            description=f"{member.mention}, sunucuyu tam olarak kullanabilmek için doğrulama butonuna basmayı unutma.",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    member = message.author
    is_mod = member.guild_permissions.administrator
    
    if not is_mod:
        db = load_db()
        
        if db.get("lockdown"):
            unverified_role = message.guild.get_role(UNVERIFIED_ROLE_ID)
            if unverified_role and unverified_role in member.roles:
                try:
                    await message.delete()
                except:
                    pass
                return
        
        lowered = message.content.lower()
        if "discord.gg/" in lowered or "discord.com/invite/" in lowered:
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {member.mention} davet linki paylaşamazsın!", delete_after=5)
            except:
                pass
            return
        
        if any(word in lowered for word in BANNED_WORDS):
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {member.mention} mesajın yasaklı kelime içeriyor!", delete_after=5)
            except:
                pass
            return
        
        now = time.time()
        times = message_times[member.id]
        times.append(now)
        if len(times) == SPAM_MESSAGE_LIMIT and (now - times[0]) <= SPAM_TIME_WINDOW:
            try:
                await member.timeout(timedelta(minutes=SPAM_TIMEOUT_MINUTES), reason="Otomatik anti-spam")
                await message.channel.send(f"🔇 {member.mention} spam yaptığı için {SPAM_TIMEOUT_MINUTES} dakika susturuldu.")
            except:
                pass
            times.clear()
    
    await bot.process_commands(message)

# ======================================================================
# BAŞLAT
# ======================================================================
if __name__ == "__main__":
    print("🛡️ Yigit Güvenlik Botu başlatılıyor...")
    bot.run(TOKEN)
