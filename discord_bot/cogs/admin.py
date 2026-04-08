"""
Admin slash commands: channel configuration, status, purge.
"""

import discord
from discord import app_commands
from discord.ext import commands
from .utils import load_config, save_config


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setchannel", description="Set the channel for SD image uploads (webhook)")
    @is_admin()
    async def set_upload_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config["upload_channel_id"] = channel.id
        save_config(config)
        await interaction.response.send_message(f"Upload channel set to {channel.mention}", ephemeral=True)

    @app_commands.command(name="setlistenchannel", description="Set the channel to listen for PNG info strings")
    @is_admin()
    async def set_listen_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        config = load_config()
        config["listen_channel_id"] = channel.id
        save_config(config)
        await interaction.response.send_message(
            f"PNG info listen channel set to {channel.mention}\n"
            f"Paste a PNG info string there and I'll generate the image!",
            ephemeral=True,
        )

    @app_commands.command(name="sdstatus", description="Show the current bot configuration")
    @is_admin()
    async def sd_status(self, interaction: discord.Interaction):
        config = load_config()

        def fmt_channel(cid):
            return f"<#{cid}>" if cid else "Not set"

        embed = discord.Embed(title="SD Discord Bot Status", color=0x5865F2)
        embed.add_field(name="Upload Channel", value=fmt_channel(config.get("upload_channel_id")), inline=False)
        embed.add_field(name="Listen Channel", value=fmt_channel(config.get("listen_channel_id")), inline=False)
        embed.add_field(
            name="SD API URL",
            value=f"`{config.get('sd_api_url', 'http://127.0.0.1:7860')}`",
            inline=False,
        )
        embed.add_field(name="Bot Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setsdapi", description="Set the reForge API URL")
    @is_admin()
    async def set_sd_api(self, interaction: discord.Interaction, url: str):
        config = load_config()
        config["sd_api_url"] = url.rstrip("/")
        save_config(config)
        await interaction.response.send_message(f"SD API URL set to `{url}`", ephemeral=True)

    @app_commands.command(name="purge", description="Delete recent messages from the upload channel")
    @is_admin()
    async def purge(self, interaction: discord.Interaction, count: int = 10):
        config = load_config()
        channel_id = config.get("upload_channel_id")
        if not channel_id:
            await interaction.response.send_message("Upload channel is not set.", ephemeral=True)
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Upload channel not found.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await channel.purge(limit=count)
        await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

    @set_upload_channel.error
    @set_listen_channel.error
    @sd_status.error
    @set_sd_api.error
    @purge.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Administrator permission required.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Error: {error}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
