import discord
from discord import app_commands
from datetime import datetime

TOKEN = 'REMOVED'

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Commands synced!")

bot = MyBot()

meetings = []
meeting_counter = 0

tasks = []
task_counter = 0

@bot.event
async def on_ready():
    print(f'{bot.user.name} is online!')
    print('Bot is ready!')

# Modal for Online location
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
        global meeting_counter
        meeting_counter += 1
        meeting_id = meeting_counter

        # Save meeting
        meeting = {
            'id': meeting_id,
            'subject': self.meeting_data['subject'],
            'date': self.meeting_data['date'],
            'time': self.meeting_data['time'],
            'type': 'Online',
            'location': self.location.value,
            'creator': interaction.user,
            'creator_mention': interaction.user.mention,
            'attendees': [interaction.user.id]
        }
        meetings.append(meeting)

        # Create embed for meeting announcement
        embed = discord.Embed(
            title=f"📅 New Meeting: {meeting['subject']}",
            description=f"React with ✅ to join this meeting!",
            color=discord.Color.blue()
        )
        embed.add_field(name="📆 Date", value=meeting['date'], inline=True)
        embed.add_field(name="⏰ Time", value=meeting['time'], inline=True)
        embed.add_field(name="🌐 Location", value=f"Online - {meeting['location']}", inline=False)
        embed.add_field(name="👤 Created by", value=meeting['creator_mention'], inline=True)
        embed.add_field(name="👥 Attendees", value=meeting['creator_mention'], inline=False)
        embed.set_footer(text=f"Meeting ID: {meeting_id}")

        # Send to channel with @everyone ping
        channel = interaction.channel
        await channel.send(content="@everyone", embed=embed)
        
        await interaction.response.send_message(
            f"✅ Meeting created successfully! (ID: {meeting_id})",
            ephemeral=True
        )

# Modal for On-Campus location
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
        global meeting_counter
        meeting_counter += 1
        meeting_id = meeting_counter

        # Save meeting
        meeting = {
            'id': meeting_id,
            'subject': self.meeting_data['subject'],
            'date': self.meeting_data['date'],
            'time': self.meeting_data['time'],
            'type': 'On-Campus',
            'location': self.location.value,
            'creator': interaction.user,
            'creator_mention': interaction.user.mention,
            'attendees': [interaction.user.id]
        }
        meetings.append(meeting)

        # Create embed for meeting announcement
        embed = discord.Embed(
            title=f"📅 New Meeting: {meeting['subject']}",
            description=f"React with ✅ to join this meeting!",
            color=discord.Color.green()
        )
        embed.add_field(name="📆 Date", value=meeting['date'], inline=True)
        embed.add_field(name="⏰ Time", value=meeting['time'], inline=True)
        embed.add_field(name="🏫 Location", value=f"On-Campus - {meeting['location']}", inline=False)
        embed.add_field(name="👤 Created by", value=meeting['creator_mention'], inline=True)
        embed.add_field(name="👥 Attendees", value=meeting['creator_mention'], inline=False)
        embed.set_footer(text=f"Meeting ID: {meeting_id}")

        # Send to channel with @everyone ping
        channel = interaction.channel
        await channel.send(content="@everyone", embed=embed)
        
        await interaction.response.send_message(
            f"✅ Meeting created successfully! (ID: {meeting_id})",
            ephemeral=True
        )

# View for Online/On-Campus buttons
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

@bot.tree.command(name="create-meeting", description="Create a new study meeting")
@app_commands.describe(
    subject="What is the meeting about?",
    date="Date (DD-MM-YYYY)",
    time="Time (HH:MM)"
)
async def create_meeting(interaction: discord.Interaction, subject: str, date: str, time: str):
    try:
        meeting_datetime = datetime.strptime(f"{date} {time}", "%d-%m-%Y %H:%M")
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid date or time format! Use DD-MM-YYYY for date and HH:MM for time.",
            ephemeral=True
        )
        return
    
    meeting_data = {
        'subject': subject,
        'date': date,
        'time': time
    }
    
    view = LocationView(meeting_data)
    await interaction.response.send_message(
        f"Creating meeting: **{subject}**\n📅 {date} at {time}\n\nWhere will this meeting take place?",
        view=view,
        ephemeral=True
    )

# Priority choices for tasks
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
    assignee: discord.User
):
    # Validate date and time format
    try:
        task_datetime = datetime.strptime(f"{due_date} {due_time}", "%d-%m-%Y %H:%M")
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid date or time format! Use DD-MM-YYYY for date and HH:MM for time.",
            ephemeral=True
        )
        return

    global task_counter
    task_counter += 1
    task_id = task_counter

    # Create task
    task = {
        'id': task_id,
        'title': title,
        'description': description,
        'due_date': due_date,
        'due_time': due_time,
        'priority': priority.value,
        'assignee': assignee,
        'assignee_mention': assignee.mention,
        'creator': interaction.user,
        'creator_mention': interaction.user.mention,
        'status': 'Pending',
        'created_at': datetime.now()
    }
    tasks.append(task)

    # Set color based on priority
    if priority.value == "High":
        color = discord.Color.red()
    elif priority.value == "Medium":
        color = discord.Color.orange()
    else:
        color = discord.Color.green()

    # Create embed for task announcement
    priority_emoji = "🔴" if priority.value == "High" else ("🟠" if priority.value == "Medium" else "🟢")
    embed = discord.Embed(
        title=f"📋 New Task: {task['title']}",
        description=task['description'],
        color=color
    )
    embed.add_field(name="📅 Due Date", value=task['due_date'], inline=True)
    embed.add_field(name="⏰ Due Time", value=task['due_time'], inline=True)
    embed.add_field(name="⚡ Priority", value=f"{priority_emoji} {priority.value}", inline=True)
    embed.add_field(name="👤 Assigned to", value=task['assignee_mention'], inline=True)
    embed.add_field(name="👤 Created by", value=task['creator_mention'], inline=True)
    embed.add_field(name="📊 Status", value="⏳ Pending", inline=True)
    embed.set_footer(text=f"Task ID: {task_id}")

    # Send to channel with @everyone ping
    channel = interaction.channel
    await channel.send(content="@everyone", embed=embed)

    await interaction.response.send_message(
        f"✅ Task created successfully! (ID: {task_id})",
        ephemeral=True
    )

# Status choices for listing tasks
status_choices = [
    app_commands.Choice(name="All Tasks", value="All"),
    app_commands.Choice(name="⏳ Pending", value="Pending"),
    app_commands.Choice(name="✅ Completed", value="Completed")
]

@bot.tree.command(name="list-tasks", description="View all tasks")
@app_commands.describe(status="Filter tasks by status")
@app_commands.choices(status=status_choices)
async def list_tasks(interaction: discord.Interaction, status: app_commands.Choice[str] = None):
    # Default to "All" if no status specified
    filter_status = status.value if status else "All"

    # Filter tasks based on status
    if filter_status == "All":
        filtered_tasks = tasks
    else:
        filtered_tasks = [task for task in tasks if task['status'] == filter_status]

    # Check if there are any tasks
    if not filtered_tasks:
        await interaction.response.send_message(
            f"📋 No {filter_status.lower()} tasks found.",
            ephemeral=True
        )
        return

    # Create embed for tasks
    embed = discord.Embed(
        title=f"📋 Task List - {filter_status}",
        description=f"Total: {len(filtered_tasks)} task(s)",
        color=discord.Color.blue()
    )

    # Add each task as a field (limit to 10 tasks per embed due to Discord limits)
    for task in filtered_tasks[:10]:
        priority_emoji = "🔴" if task['priority'] == "High" else ("🟠" if task['priority'] == "Medium" else "🟢")
        status_emoji = "✅" if task['status'] == "Completed" else "⏳"

        task_info = (
            f"**Description:** {task['description']}\n"
            f"**Due:** {task['due_date']} at {task['due_time']}\n"
            f"**Priority:** {priority_emoji} {task['priority']}\n"
            f"**Assigned to:** {task['assignee_mention']}\n"
            f"**Status:** {status_emoji} {task['status']}\n"
            f"**Created by:** {task['creator_mention']}"
        )

        embed.add_field(
            name=f"ID: {task['id']} - {task['title']}",
            value=task_info,
            inline=False
        )

    if len(filtered_tasks) > 10:
        embed.set_footer(text=f"Showing first 10 of {len(filtered_tasks)} tasks")

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="complete-task", description="Mark a task as completed")
@app_commands.describe(task_id="ID of the task to complete")
async def complete_task(interaction: discord.Interaction, task_id: int):
    # Find the task
    task = None
    for t in tasks:
        if t['id'] == task_id:
            task = t
            break

    if not task:
        await interaction.response.send_message(
            f"❌ Task with ID {task_id} not found.",
            ephemeral=True
        )
        return

    # Check if task is already completed
    if task['status'] == "Completed":
        await interaction.response.send_message(
            f"ℹ️ Task {task_id} is already completed.",
            ephemeral=True
        )
        return

    # Check permissions: only assignee or creator can complete
    if interaction.user.id != task['assignee'].id and interaction.user.id != task['creator'].id:
        await interaction.response.send_message(
            f"❌ You don't have permission to complete this task. Only the assignee or creator can complete it.",
            ephemeral=True
        )
        return

    # Mark task as completed
    task['status'] = "Completed"

    # Create completion announcement embed
    embed = discord.Embed(
        title=f"✅ Task Completed: {task['title']}",
        description=task['description'],
        color=discord.Color.green()
    )
    embed.add_field(name="📋 Task ID", value=str(task['id']), inline=True)
    embed.add_field(name="👤 Completed by", value=interaction.user.mention, inline=True)
    embed.add_field(name="👤 Assigned to", value=task['assignee_mention'], inline=True)
    embed.set_footer(text="Task marked as completed")

    # Send announcement to channel
    channel = interaction.channel
    await channel.send(embed=embed)

    await interaction.response.send_message(
        f"✅ Task {task_id} marked as completed!",
        ephemeral=True
    )

@bot.tree.command(name="delete-task", description="Delete a task")
@app_commands.describe(task_id="ID of the task to delete")
async def delete_task(interaction: discord.Interaction, task_id: int):
    # Find the task
    task = None
    task_index = None
    for i, t in enumerate(tasks):
        if t['id'] == task_id:
            task = t
            task_index = i
            break

    if not task:
        await interaction.response.send_message(
            f"❌ Task with ID {task_id} not found.",
            ephemeral=True
        )
        return

    # Check permissions: only creator or admins can delete
    is_creator = interaction.user.id == task['creator'].id
    is_admin = interaction.user.guild_permissions.administrator

    if not is_creator and not is_admin:
        await interaction.response.send_message(
            f"❌ You don't have permission to delete this task. Only the creator or administrators can delete it.",
            ephemeral=True
        )
        return

    # Delete the task
    deleted_task = tasks.pop(task_index)

    # Send confirmation to channel
    embed = discord.Embed(
        title=f"🗑️ Task Deleted: {deleted_task['title']}",
        description=f"Task ID {task_id} has been deleted by {interaction.user.mention}",
        color=discord.Color.red()
    )
    embed.add_field(name="📋 Task", value=deleted_task['description'], inline=False)

    channel = interaction.channel
    await channel.send(embed=embed)

    await interaction.response.send_message(
        f"✅ Task {task_id} has been deleted successfully!",
        ephemeral=True
    )

@bot.tree.command(name="ping", description="Test if bot is working")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot is working!")

@bot.tree.command(name="claudiu", description="asd")
async def thea(interaction: discord.Interaction):
    await interaction.response.send_message("You have a fatass")

bot.run(TOKEN)