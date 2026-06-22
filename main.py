"""
main.py
=======
The entry point. Run the whole bot with:

    python main.py

Logging is configured inside run_bot(); we keep one friendly print here so the
terminal shows something immediately even before logging spins up.
"""

from config import Config
from bot import run_bot


def main() -> None:
    print(f"🚀 Starting {Config.BOT_NAME}... (prefix '{Config.PREFIX}', slash commands enabled)")
    try:
        run_bot()
    except KeyboardInterrupt:
        # Graceful shutdown when you press Ctrl+C in the terminal.
        print(f"\n👋 {Config.BOT_NAME} shutting down. See you next session!")


if __name__ == "__main__":
    main()
