
import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

async def get_db():
    return await asyncpg.connect(**DB_CONFIG)

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await create_tables()
        await self.tree.sync()
        check_reminders.start()  # Start the reminder background task
        print("Commands synced!")

bot = MyBot()

# ==================== DATABASE SETUP ====================

async def create_tables():
    conn = await get_db()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS meetings (
                id SERIAL PRIMARY KEY,
                subject TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                type TEXT NOT NULL,
                location TEXT NOT NULL,
                creator_id BIGINT NOT NULL,
                creator_name TEXT NOT NULL,
                channel_id BIGINT,
                reminded BOOLEAN DEFAULT FALSE
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS attendees (
                meeting_id INTEGER REFERENCES meetings(id),
                user_id BIGINT NOT NULL,
                user_name TEXT NOT NULL
            )
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                due_date TEXT NOT NULL,
                due_time TEXT NOT NULL,
                priority TEXT NOT NULL,
                assignee_id BIGINT NOT NULL,
                assignee_name TEXT NOT NULL,
                creator_id BIGINT NOT NULL,
                creator_name TEXT NOT NULL,
                status TEXT DEFAULT 'Pending'
            )
        ''')
        print("Database tables ready!")
    finally:
        await conn.close()

# ==================== AUTO REMINDER ====================

@tasks.loop(minutes=1)  # Runs every minute
async def check_reminders():
    now = datetime.now()
    reminder_time = now + timedelta(hours=24)  # 24 hours from now

    conn = await get_db()
    try:
        # Find meetings happening in ~24 hours that haven't been reminded yet
        meetings = await conn.fetch('''
            SELECT * FROM meetings
            WHERE reminded = FALSE
        ''')

        for meeting in meetings:
            # Parse meeting datetime
            try:
                meeting_dt = datetime.strptime(
                    f"{meeting['date']} {meeting['time']}", "%d-%m-%Y %H:%M"
                )
            except:
                continue

            # Check if meeting is within the next 24 hours (with 1 min tolerance)
            time_diff = meeting_dt - now
            hours_until = time_diff.total_seconds() / 3600

            if 23.9 <= hours_until <= 24.1:  # Between 23h54m and 24h6m
                # Get the channel
                channel = bot.get_channel(meeting['channel_id'])
                if channel:
                    # Get attendees
                    attendees = await conn.fetch(
                        'SELECT user_name FROM attendees WHERE meeting_id = $1',
                        meeting['id']
                    )
                    attendee_list = ", ".join([a['user_name'] for a in attendees]) or "No attendees yet"

                    # Send reminder
                    type_emoji = "🌐" if meeting['type'] == "Online" else "🏫"
                    embed = discord.Embed(
                        title=f"⏰ Meeting Reminder: {meeting['subject']}",
                        description="This meeting is happening **tomorrow**!",
                        color=discord.Color.yellow()
                    )
                    embed.add_field(name="📆 Date", value=meeting['date'], inline=True)
                    embed.add_field(name="⏰ Time", value=meeting['time'], inline=True)
                    embed.add_field(name=f"{type_emoji} Location", value=f"{meeting['type']} - {meeting['location']}", inline=False)
                    embed.add_field(name="👥 Attendees", value=attendee_list, inline=False)
                    embed.set_footer(text=f"Meeting ID: {meeting['id']}")

                    await channel.send(content="@everyone", embed=embed)

                    # Mark as reminded so we don't send it again
                    await conn.execute(
                        'UPDATE meetings SET reminded = TRUE WHERE id = $1',
                        meeting['id']
                    )
                    print(f"Reminder sent for meeting {meeting['id']}: {meeting['subject']}")

    finally:
        await conn.close()

@check_reminders.before_loop
async def before_check_reminders():
    await bot.wait_until_ready()  # Wait for bot to be ready before starting

# ==================== BOT EVENTS ====================

@bot.event
async def on_ready():
    print(f'{bot.user.name} is online!')
    print('Bot is ready!')
    print('Auto-reminder is running!')

# ==================== MEETING MODALS ====================

class OnlineLocationModal(discord.ui.Modal, title='Online Meeting Location'):
    location = discord.ui.TextInput(
        label='Voice Channel or Link',
        placeholder='e.g., General Voice or discord.gg/...',
        required=True,
        max_length=200
    )

    def __init__(self, meeting_data):
        super().__init__()
        self.meeting_data = meeting_data

    async def on_submit(self, interaction: discord.Interaction):
        conn = await get_db()
        try:
            meeting_id = await conn.fetchval('''
                INSERT INTO meetings (subject, date, time, type, location, creator_id, creator_name, channel_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
            ''', self.meeting_data['subject'], self.meeting_data['date'],
                self.meeting_data['time'], 'Online', self.location.value,
                interaction.user.id, interaction.user.display_name,
                interaction.channel_id)  # Save channel ID!

            await conn.execute('''
                INSERT INTO attendees (meeting_id, user_id, user_name)
                VALUES ($1, $2, $3)
            ''', meeting_id, interaction.user.id, interaction.user.display_name)
        finally:
            await conn.close()

        embed = discord.Embed(
            title=f"📅 New Meeting: {self.meeting_data['subject']}",
            description="Click ✅ Join Meeting to attend!",
            color=discord.Color.blue()
        )
        embed.add_field(name="📆 Date", value=self.meeting_data['date'], inline=True)
        embed.add_field(name="⏰ Time", value=self.meeting_data['time'], inline=True)
        embed.add_field(name="🌐 Location", value=f"Online - {self.location.value}", inline=False)
        embed.add_field(name="👤 Created by", value=interaction.user.mention, inline=True)
        embed.add_field(name="👥 Attendees", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Meeting ID: {meeting_id}")

        await interaction.channel.send(content="@everyone New meeting created!", embed=embed)
        await interaction.response.send_message(f"✅ Meeting created! (ID: {meeting_id})", ephemeral=True)


class OnCampusLocationModal(discord.ui.Modal, title='On-Campus Meeting Location'):
    location = discord.ui.TextInput(
        label='Building and Room',
        placeholder='e.g., Building A, Room 301',
        required=True,
        max_length=200
    )

    def __init__(self, meeting_data):
        super().__init__()
        self.meeting_data = meeting_data

    async def on_submit(self, interaction: discord.Interaction):
        conn = await get_db()
        try:
            meeting_id = await conn.fetchval('''
                INSERT INTO meetings (subject, date, time, type, location, creator_id, creator_name, channel_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
            ''', self.meeting_data['subject'], self.meeting_data['date'],
                self.meeting_data['time'], 'On-Campus', self.location.value,
                interaction.user.id, interaction.user.display_name,
                interaction.channel_id)  # Save channel ID!

            await conn.execute('''
                INSERT INTO attendees (meeting_id, user_id, user_name)
                VALUES ($1, $2, $3)
            ''', meeting_id, interaction.user.id, interaction.user.display_name)
        finally:
            await conn.close()

        embed = discord.Embed(
            title=f"📅 New Meeting: {self.meeting_data['subject']}",
            description="Click ✅ Join Meeting to attend!",
            color=discord.Color.green()
        )
        embed.add_field(name="📆 Date", value=self.meeting_data['date'], inline=True)
        embed.add_field(name="⏰ Time", value=self.meeting_data['time'], inline=True)
        embed.add_field(name="🏫 Location", value=f"On-Campus - {self.location.value}", inline=False)
        embed.add_field(name="👤 Created by", value=interaction.user.mention, inline=True)
        embed.add_field(name="👥 Attendees", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Meeting ID: {meeting_id}")

        await interaction.channel.send(content="@everyone New meeting created!", embed=embed)
        await interaction.response.send_message(f"✅ Meeting created! (ID: {meeting_id})", ephemeral=True)


# ==================== MEETING BUTTONS ====================

class LocationView(discord.ui.View):
    def __init__(self, meeting_data):
        super().__init__(timeout=300)
        self.meeting_data = meeting_data

    @discord.ui.button(label="🌐 Online", style=discord.ButtonStyle.primary)
    async def online_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = OnlineLocationModal(self.meeting_data)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🏫 On-Campus", style=discord.ButtonStyle.secondary)
    async def oncampus_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = OnCampusLocationModal(self.meeting_data)
        await interaction.response.send_modal(modal)


# ==================== MEETING COMMANDS ====================

@bot.tree.command(name="create-meeting", description="Create a new study meeting")
@app_commands.describe(
    subject="What is the meeting about?",
    date="Date (DD-MM-YYYY)",
    time="Time (HH:MM)"
)
async def create_meeting(interaction: discord.Interaction, subject: str, date: str, time: str):
    try:
        datetime.strptime(f"{date} {time}", "%d-%m-%Y %H:%M")
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid date or time format! Use DD-MM-YYYY for date and HH:MM for time.",
            ephemeral=True
        )
        return

    meeting_data = {'subject': subject, 'date': date, 'time': time}
    view = LocationView(meeting_data)
    await interaction.response.send_message(
        f"Creating meeting: **{subject}**\n📅 {date} at {time}\n\nWhere will this meeting take place?",
        view=view,
        ephemeral=True
    )


@bot.tree.command(name="list-meetings", description="View all upcoming meetings")
async def list_meetings(interaction: discord.Interaction):
    conn = await get_db()
    try:
        all_meetings = await conn.fetch('SELECT * FROM meetings ORDER BY date, time')
    finally:
        await conn.close()

    if not all_meetings:
        await interaction.response.send_message("📅 No meetings found.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📅 All Meetings",
        description=f"Total: {len(all_meetings)} meeting(s)",
        color=discord.Color.blue()
    )

    for meeting in all_meetings[:10]:
        type_emoji = "🌐" if meeting['type'] == "Online" else "🏫"
        embed.add_field(
            name=f"ID: {meeting['id']} - {meeting['subject']}",
            value=f"📆 {meeting['date']} at {meeting['time']}\n{type_emoji} {meeting['type']} - {meeting['location']}\n👤 Created by: {meeting['creator_name']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="join-meeting", description="Join a meeting")
@app_commands.describe(meeting_id="ID of the meeting to join")
async def join_meeting(interaction: discord.Interaction, meeting_id: int):
    conn = await get_db()
    try:
        meeting = await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)

        if not meeting:
            await interaction.response.send_message(f"❌ Meeting {meeting_id} not found.", ephemeral=True)
            return

        existing = await conn.fetchrow(
            'SELECT * FROM attendees WHERE meeting_id = $1 AND user_id = $2',
            meeting_id, interaction.user.id
        )

        if existing:
            await interaction.response.send_message("ℹ️ You already joined this meeting!", ephemeral=True)
            return

        await conn.execute(
            'INSERT INTO attendees (meeting_id, user_id, user_name) VALUES ($1, $2, $3)',
            meeting_id, interaction.user.id, interaction.user.display_name
        )

        attendees = await conn.fetch('SELECT user_name FROM attendees WHERE meeting_id = $1', meeting_id)
    finally:
        await conn.close()

    attendee_list = ", ".join([a['user_name'] for a in attendees])

    embed = discord.Embed(
        title=f"✅ {interaction.user.display_name} joined: {meeting['subject']}",
        color=discord.Color.green()
    )
    embed.add_field(name="📆 Date", value=meeting['date'], inline=True)
    embed.add_field(name="⏰ Time", value=meeting['time'], inline=True)
    embed.add_field(name="👥 Attendees", value=attendee_list, inline=False)
    embed.set_footer(text=f"Meeting ID: {meeting_id}")

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"✅ You joined meeting {meeting_id}!", ephemeral=True)


@bot.tree.command(name="cancel-meeting", description="Cancel your meeting")
@app_commands.describe(meeting_id="ID of the meeting to cancel")
async def cancel_meeting(interaction: discord.Interaction, meeting_id: int):
    conn = await get_db()
    try:
        meeting = await conn.fetchrow('SELECT * FROM meetings WHERE id = $1', meeting_id)

        if not meeting:
            await interaction.response.send_message(f"❌ Meeting {meeting_id} not found.", ephemeral=True)
            return

        if interaction.user.id != meeting['creator_id']:
            await interaction.response.send_message(
                "❌ Only the creator can cancel this meeting.", ephemeral=True
            )
            return

        await conn.execute('DELETE FROM attendees WHERE meeting_id = $1', meeting_id)
        await conn.execute('DELETE FROM meetings WHERE id = $1', meeting_id)
    finally:
        await conn.close()

    embed = discord.Embed(
        title=f"❌ Meeting Cancelled: {meeting['subject']}",
        description=f"Meeting on {meeting['date']} at {meeting['time']} has been cancelled by {interaction.user.mention}",
        color=discord.Color.red()
    )
    await interaction.channel.send(content="@everyone", embed=embed)
    await interaction.response.send_message(f"✅ Meeting {meeting_id} cancelled.", ephemeral=True)


# ==================== TASK COMMANDS ====================

priority_choices = [
    app_commands.Choice(name="🔴 High", value="High"),
    app_commands.Choice(name="🟠 Medium", value="Medium"),
    app_commands.Choice(name="🟢 Low", value="Low")
]

@bot.tree.command(name="add-task", description="Create a new task")
@app_commands.describe(
    title="Task title",
    description="Detailed description of the task",
    due_date="Due date (DD-MM-YYYY)",
    due_time="Due time (HH:MM)",
    priority="Priority level",
    assignee="User to assign this task to"
)
@app_commands.choices(priority=priority_choices)
async def add_task(
    interaction: discord.Interaction,
    title: str,
    description: str,
    due_date: str,
    due_time: str,
    priority: app_commands.Choice[str],
    assignee: discord.Member
):
    try:
        datetime.strptime(f"{due_date} {due_time}", "%d-%m-%Y %H:%M")
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid date or time format! Use DD-MM-YYYY for date and HH:MM for time.",
            ephemeral=True
        )
        return

    conn = await get_db()
    try:
        task_id = await conn.fetchval('''
            INSERT INTO tasks (title, description, due_date, due_time, priority, assignee_id, assignee_name, creator_id, creator_name)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING id
        ''', title, description, due_date, due_time, priority.value,
            assignee.id, assignee.display_name,
            interaction.user.id, interaction.user.display_name)
    finally:
        await conn.close()

    priority_emoji = "🔴" if priority.value == "High" else ("🟠" if priority.value == "Medium" else "🟢")
    color = discord.Color.red() if priority.value == "High" else (discord.Color.orange() if priority.value == "Medium" else discord.Color.green())

    embed = discord.Embed(title=f"📋 New Task: {title}", description=description, color=color)
    embed.add_field(name="📅 Due Date", value=due_date, inline=True)
    embed.add_field(name="⏰ Due Time", value=due_time, inline=True)
    embed.add_field(name="⚡ Priority", value=f"{priority_emoji} {priority.value}", inline=True)
    embed.add_field(name="👤 Assigned to", value=assignee.mention, inline=True)
    embed.add_field(name="👤 Created by", value=interaction.user.mention, inline=True)
    embed.add_field(name="📊 Status", value="⏳ Pending", inline=True)
    embed.set_footer(text=f"Task ID: {task_id}")

    await interaction.channel.send(content="@everyone", embed=embed)
    await interaction.response.send_message(f"✅ Task created! (ID: {task_id})", ephemeral=True)


status_choices = [
    app_commands.Choice(name="All Tasks", value="All"),
    app_commands.Choice(name="⏳ Pending", value="Pending"),
    app_commands.Choice(name="✅ Completed", value="Completed")
]

@bot.tree.command(name="list-tasks", description="View all tasks")
@app_commands.describe(status="Filter tasks by status")
@app_commands.choices(status=status_choices)
async def list_tasks(interaction: discord.Interaction, status: app_commands.Choice[str] = None):
    filter_status = status.value if status else "All"

    conn = await get_db()
    try:
        if filter_status == "All":
            all_tasks = await conn.fetch('SELECT * FROM tasks ORDER BY due_date, due_time')
        else:
            all_tasks = await conn.fetch(
                'SELECT * FROM tasks WHERE status = $1 ORDER BY due_date, due_time', filter_status
            )
    finally:
        await conn.close()

    if not all_tasks:
        await interaction.response.send_message(f"📋 No {filter_status.lower()} tasks found.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📋 Task List - {filter_status}",
        description=f"Total: {len(all_tasks)} task(s)",
        color=discord.Color.blue()
    )

    for task in all_tasks[:10]:
        priority_emoji = "🔴" if task['priority'] == "High" else ("🟠" if task['priority'] == "Medium" else "🟢")
        status_emoji = "✅" if task['status'] == "Completed" else "⏳"
        embed.add_field(
            name=f"ID: {task['id']} - {task['title']}",
            value=(
                f"**Description:** {task['description']}\n"
                f"**Due:** {task['due_date']} at {task['due_time']}\n"
                f"**Priority:** {priority_emoji} {task['priority']}\n"
                f"**Assigned to:** {task['assignee_name']}\n"
                f"**Status:** {status_emoji} {task['status']}\n"
                f"**Created by:** {task['creator_name']}"
            ),
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="complete-task", description="Mark a task as completed")
@app_commands.describe(task_id="ID of the task to complete")
async def complete_task(interaction: discord.Interaction, task_id: int):
    conn = await get_db()
    try:
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)

        if not task:
            await interaction.response.send_message(f"❌ Task {task_id} not found.", ephemeral=True)
            return

        if task['status'] == "Completed":
            await interaction.response.send_message(f"ℹ️ Task {task_id} is already completed.", ephemeral=True)
            return

        if interaction.user.id != task['assignee_id'] and interaction.user.id != task['creator_id']:
            await interaction.response.send_message(
                "❌ Only the assignee or creator can complete this task.", ephemeral=True
            )
            return

        await conn.execute("UPDATE tasks SET status = 'Completed' WHERE id = $1", task_id)
    finally:
        await conn.close()

    embed = discord.Embed(
        title=f"✅ Task Completed: {task['title']}",
        description=task['description'],
        color=discord.Color.green()
    )
    embed.add_field(name="📋 Task ID", value=str(task_id), inline=True)
    embed.add_field(name="👤 Completed by", value=interaction.user.mention, inline=True)
    embed.add_field(name="👤 Assigned to", value=task['assignee_name'], inline=True)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Task {task_id} marked as completed!", ephemeral=True)


@bot.tree.command(name="delete-task", description="Delete a task")
@app_commands.describe(task_id="ID of the task to delete")
async def delete_task(interaction: discord.Interaction, task_id: int):
    conn = await get_db()
    try:
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)

        if not task:
            await interaction.response.send_message(f"❌ Task {task_id} not found.", ephemeral=True)
            return

        is_creator = interaction.user.id == task['creator_id']
        is_admin = interaction.user.guild_permissions.administrator

        if not is_creator and not is_admin:
            await interaction.response.send_message(
                "❌ Only the creator or an admin can delete this task.", ephemeral=True
            )
            return

        await conn.execute('DELETE FROM tasks WHERE id = $1', task_id)
    finally:
        await conn.close()

    embed = discord.Embed(
        title=f"🗑️ Task Deleted: {task['title']}",
        description=f"Task ID {task_id} deleted by {interaction.user.mention}",
        color=discord.Color.red()
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Task {task_id} deleted!", ephemeral=True)


# ==================== FUN COMMANDS ====================

@bot.tree.command(name="ping", description="Test if bot is working")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot is working!")

@bot.tree.command(name="ping", description="Test if bot is working")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot is working!")


@bot.tree.command(name="commands", description="Display all available bot commands")
async def commands(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands for this bot:",
        color=discord.Color.purple()
    )

    # Meeting Commands
    embed.add_field(
        name="📅 Meeting Commands",
        value=(
            "`/create-meeting` - Create a new study meeting\n"
            "`/list-meetings` - View all upcoming meetings\n"
            "`/join-meeting` - Join a meeting by ID\n"
            "`/cancel-meeting` - Cancel your meeting"
        ),
        inline=False
    )

    # Task Commands
    embed.add_field(
        name="📋 Task Commands",
        value=(
            "`/add-task` - Create a new task\n"
            "`/list-tasks` - View all tasks (filter by status)\n"
            "`/complete-task` - Mark a task as completed\n"
            "`/delete-task` - Delete a task"
        ),
        inline=False
    )

    # Utility Commands
    embed.add_field(
        name="🛠️ Utility Commands",
        value=(
            "`/commands` - Display this help message\n"
            "`/ping` - Test if bot is working"
        ),
        inline=False
    )

    embed.set_footer(text="Study Manager Bot | Need help with a specific command? Just try it!")

    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(TOKEN)