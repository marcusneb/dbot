# dbot - Study Manager Discord Bot

Univeristy group-work usually starts on discord, and ends up on other apps for organizing the tasks, meetings etc. So I figured I should solve this problem somehow.
Here's my approach:

A Discord bot for organizing study group meetings and team tasks. Built with `discord.py` and PostgreSQL, it lets students schedule meetings (online or on-campus), track attendees, assign prioritized tasks, and get automatic 24-hour meeting reminders.

## Features

- **Meeting management** - create, list, join, and cancel study meetings with date/time validation and online or on-campus locations.
- **Task management** - assign tasks to members with due dates, priority levels (High / Medium / Low), and status tracking (Pending / Completed).
- **Automatic reminders** - a background task runs every minute and pings `@everyone` in the meeting's channel 24 hours before it starts.
- **Slash commands** - all commands use Discord's native `/` command interface.
- **Rich embeds** - responses use color-coded embeds with emojis for readability.

## Commands

| Command | Description |
| --- | --- |
| `/create-meeting` | Create a new study meeting (prompts for Online/On-Campus location) |
| `/list-meetings` | View all upcoming meetings |
| `/join-meeting` | Join a meeting by ID |
| `/cancel-meeting` | Cancel a meeting you created |
| `/add-task` | Create a new task and assign it to a member |
| `/list-tasks` | View all tasks, optionally filtered by status |
| `/complete-task` | Mark a task as completed |
| `/delete-task` | Delete a task (creator or admin only) |
| `/commands` | Show the full command list |
| `/ping` | Check if the bot is online |

## Requirements

- Python 3.10+
- PostgreSQL 13+
- A Discord bot application and token ([Discord Developer Portal](https://discord.com/developers/applications))

Python dependencies:

```
discord.py
asyncpg
```

Install them with:

```bash
pip install discord.py asyncpg
```

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/<your-username>/dbot.git
   cd dbot
   ```

2. **Create the PostgreSQL database**
   ```sql
   CREATE DATABASE study_manager;
   ```
   The bot creates its `meetings`, `attendees`, and `tasks` tables automatically on first run.

3. **Configure credentials**

   Open `dbot/bot.py` and set your Discord bot token and PostgreSQL credentials. For safety, load them from environment variables rather than hardcoding:

   ```python
   import os
   TOKEN = os.getenv("DISCORD_TOKEN")
   DB_CONFIG = {
       "host": os.getenv("DB_HOST", "localhost"),
       "port": int(os.getenv("DB_PORT", 5432)),
       "database": os.getenv("DB_NAME", "study_manager"),
       "user": os.getenv("DB_USER", "postgres"),
       "password": os.getenv("DB_PASSWORD"),
   }
   ```

4. **Invite the bot to your server**

   In the Discord Developer Portal, enable the `applications.commands` and `bot` scopes, and grant the bot permission to read/send messages and mention `@everyone`. Use the generated OAuth2 URL to invite it.

5. **Run the bot**
   ```bash
   python dbot/bot.py
   ```

   On startup you should see `Database tables ready!`, `Commands synced!`, and `Bot is ready!`.

## Date & Time Format

- Dates: `DD-MM-YYYY` (e.g. `25-12-2026`)
- Times: `HH:MM` in 24-hour format (e.g. `14:30`)

## Project Structure

```
dbot/
├── dbot/
│   └── bot.py          # Main bot code
└── README.md
```

## License

MIT - feel free to fork and adapt for your own study group.
