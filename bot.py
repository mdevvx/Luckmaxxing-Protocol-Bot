import asyncio
import os
import sys

import discord
from discord.ext import commands

import config
from utils.logger import logger


class LuckmaxxingBot(commands.Bot):
    """Main bot class."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix=["!", "$"],  # $sync registers commands to a guild
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

        self.initial_extensions = [
            "cogs.protocol",
            "cogs.admin",
        ]

    async def setup_hook(self):
        """Load cogs before the bot connects."""
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as exc:
                logger.error(f"Failed to load {ext}: {exc}", exc_info=True)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} server(s)")

        # await self.change_presence(
        #     activity=discord.Activity(
        #         type=discord.ActivityType.watching,
        #         name="the gamblors train",
        #     )
        # )

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(
            f"Joined guild: {guild.name} ({guild.id}), members: {guild.member_count}"
        )
        if guild.system_channel:
            embed = discord.Embed(
                title="Luckmaxxing Protocol has arrived",
                description=(
                    "Ready to transform your members into statistical anomalies.\n\n"
                    "**Quick start**\n"
                    "1. `/configure role:<role> completion_role:<role> threads_channel:<channel>` — set enrollment role, completion role, and threads channel\n"
                    "2. `/setup` — post the enrollment message\n"
                    "3. `/generateid count:10` — create enrollment codes for your members\n\n"
                    "Gorillions await."
                ),
                color=config.EMBED_COLOR,
            )
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"Removed from guild: {guild.name} ({guild.id})")

    async def on_error(self, event: str, *args, **kwargs):
        logger.error(f"Unhandled error in event '{event}'", exc_info=True)


async def main():
    os.makedirs("logs", exist_ok=True)

    logger.info("=" * 50)
    logger.info("LUCKMAXXING PROTOCOL BOT — STARTING")
    logger.info("=" * 50)

    try:
        config.validate_config()
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    bot = LuckmaxxingBot()

    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
    except discord.LoginFailure:
        logger.error("Invalid DISCORD_BOT_TOKEN")
    except Exception as exc:
        logger.error(f"Fatal error: {exc}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("Bot shut down")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
