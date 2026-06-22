"""
main.py
=======
The entry point. Run the whole bot with:

    python main.py

This file stays deliberately tiny: it prints a startup line, hands off to
bot.run_bot(), and exits cleanly on Ctrl+C.
"""

from config import Config
from bot import run_bot


def main() -> None:
    print(f"🚀 Starting {Config.BOT_NAME}... (prefix '{Config.PREFIX}')")
    try:
        run_bot()
    except KeyboardInterrupt:
        # Graceful shutdown when you press Ctrl+C in the terminal.
        print(f"\n👋 {Config.BOT_NAME} shutting down. See you next session!")


if __name__ == "__main__":
    main()
