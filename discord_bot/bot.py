"""
Discord Bot for Stable Diffusion image management.
Receives uploaded images and provides slash commands for channel management.
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CONFIG_FILE = Path(__file__).parent / "bot_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"upload_channel_id": None, "allowed_role_ids": []}


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


class SDBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"[Bot] Slash commands synced.")

    async def on_ready(self):
        print(f"[Bot] Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Stable Diffusion generate images",
            )
        )


bot = SDBot()


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


@bot.tree.command(name="setchannel", description="Set the channel for SD image uploads")
@is_admin()
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    config = load_config()
    config["upload_channel_id"] = channel.id
    save_config(config)
    await interaction.response.send_message(
        f"Upload channel set to {channel.mention}", ephemeral=True
    )


@bot.tree.command(name="sdstatus", description="Show the current bot configuration")
@is_admin()
async def sd_status(interaction: discord.Interaction):
    config = load_config()
    channel_id = config.get("upload_channel_id")
    channel_mention = f"<#{channel_id}>" if channel_id else "Not set"

    embed = discord.Embed(title="SD Discord Bot Status", color=0x5865F2)
    embed.add_field(name="Upload Channel", value=channel_mention, inline=False)
    embed.add_field(name="Bot Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="purge", description="Delete recent SD images from the upload channel")
@is_admin()
async def purge(interaction: discord.Interaction, count: int = 10):
    config = load_config()
    channel_id = config.get("upload_channel_id")
    if not channel_id:
        await interaction.response.send_message("Upload channel is not set.", ephemeral=True)
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("Upload channel not found.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    deleted = await channel.purge(limit=count)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You need administrator permission.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)


if __name__ == "__main__":
    bot.run(BOT_TOKEN)
