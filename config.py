import os
import discord
from dotenv import load_dotenv

load_dotenv()

# ── Discord ──────────────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")

# ── Supabase ─────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# ── Video watch tracking ─────────────────────────────────────────
WATCH_BASE_URL: str = os.getenv("WATCH_BASE_URL", "https://hypergamble.bet/watch")

# ── Bot settings ─────────────────────────────────────────────────
TOTAL_DAYS: int = 8
PROTOCOL_CHANNEL_NAME: str = "luckmaxxing-protocol"
GRADUATE_ROLE_NAME: str = "Luckmaxxed Gamblor"

# ── Logging ──────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = "logs/bot.log"

# ── Embed Color ──────────────────────────────────────────────────────
EMBED_COLOR = discord.Color(0x00E79C)


def validate_config() -> bool:
    """Raise ValueError if any required environment variable is missing."""

    missing = []

    if not DISCORD_TOKEN:
        missing.append("DISCORD_BOT_TOKEN")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")

    if missing:
        raise ValueError(
            "Missing required environment variables:\n"
            + "\n".join(f"  - {k}" for k in missing)
            + "\n\nCheck your .env file."
        )

    return True
