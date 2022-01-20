import discord
from discord.ext import tasks
from discord.ext.modules import CommandCollection


class ListCollectionsCommand(discord.app.SlashCommand, name="list"):
    """Lists the loaded command collections"""

    async def callback(self):
        names = [collection.name for name, collection in self.client.command_collections.items()]

        await self.interaction.response.send_message(
            "Loaded command collections: " + ", ".join(names)
        )


class AdvancedCollection(CommandCollection):
    """My utilities collection"""

    def __init__(self, bot):
        super().__init__(bot, [ListCollectionsCommand], name="My Advanced Commands")
        self.printer_task.start()

    @tasks.loop(seconds=10)
    async def printer_task(self):
        print("I am just printing here, but could be doing something more useful")

    async def collection_check(self, command):
        if command.interaction.user.id in (123, 234, 345):
            raise Exception("This user can't use this command")

    async def handle_collection_check_error(self, command, exception):
        await command.interaction.response.send_message(
            "Sorry, you are blacklisted from using this command!", ephemeral=True
        )

    def on_unload(self):
        print("This collection is unloading. Stopping the printer task...")
        self.printer_task.cancel()


def setup(bot) -> list:
    return [AdvancedCollection(bot)]
