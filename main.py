import discord
from discord.ext import commands
import re
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# ---------- .env set up ----------
if not TOKEN:
    raise ValueError("No Discord token available in .env!")
print(f"Loaded token: {TOKEN[:5]}...")
# ----------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# --- Parse roles.txt file ---
def load_reaction_roles(file_path="roles.txt"):
    roles = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("-"):
                continue

            # Match "emoji name #hex"
            match = re.match(r"^(\S+)\s+(.+?)\s+(#[0-9A-Fa-f]{6})$", line)
            if match:
                emoji, role_name, color_hex = match.groups()
                roles[emoji] = {
                    "name": role_name,
                    "color": int(color_hex.lstrip("#"), 16),
                }
    return roles


reaction_roles = load_reaction_roles()


# --- Create or update roles ---
async def ensure_roles_exist(guild):
    for emoji, data in reaction_roles.items():
        existing = discord.utils.get(guild.roles, name=data["name"])
        if not existing:
            # Role doesn’t exist → create it
            await guild.create_role(
                name=data["name"], color=discord.Color(data["color"])
            )
            print(f"Created role: {data['name']} ({emoji})")
        else:
            # Role exists → update color if needed
            if existing.color.value != data["color"]:
                await existing.edit(color=discord.Color(data["color"]))
                print(f"Updated color for role: {data['name']}")


# --- Helper: read/write tracked message IDs ---
def get_tracked_ids():
    try:
        with open("tracked_message.txt", "r") as f:
            return [int(x.strip()) for x in f.readlines() if x.strip()]
    except FileNotFoundError:
        return []


def save_tracked_id(message_id):
    with open("tracked_message.txt", "a") as f:
        f.write(str(message_id) + "\n")


# --- Command to post the reaction messages ---
@bot.command()
async def postroles(ctx):
    await ensure_roles_exist(ctx.guild)

    emojis = list(reaction_roles.keys())
    chunk_size = 8  # number of roles per embed

    for i in range(0, len(emojis), chunk_size):
        chunk = emojis[i : i + chunk_size]
        description = "React to get a color role:\n\n"
        for emoji in chunk:
            data = reaction_roles[emoji]
            description += f"{emoji} — {data['name']}\n"

        embed = discord.Embed(
            title="Marcy's Color Roles",
            description=description,
            color=0x04943B,
        )
        message = await ctx.send(embed=embed)

        for emoji in chunk:
            await message.add_reaction(emoji)

        save_tracked_id(message.id)
        print(
            f"Posted color roles chunk ({len(chunk)} roles) → message ID {message.id}"
        )


# --- Reaction handlers ---
@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return

    tracked_ids = get_tracked_ids()
    if payload.message_id not in tracked_ids:
        return

    guild = bot.get_guild(payload.guild_id)
    emoji = str(payload.emoji)
    if emoji in reaction_roles:
        role_name = reaction_roles[emoji]["name"]
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            await payload.member.add_roles(role)
            print(f"Added {role.name} to {payload.member.display_name}")


@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    tracked_ids = get_tracked_ids()
    if payload.message_id not in tracked_ids:
        return

    emoji = str(payload.emoji)
    if emoji in reaction_roles:
        role_name = reaction_roles[emoji]["name"]
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            await member.remove_roles(role)
            print(f"❌ Removed {role.name} from {member.display_name}")


bot.run(TOKEN)
