import discord
from discord.ext.modules import CommandCollection


class HelloCommand(discord.app.SlashCommand, name="hello"):
    """Responds with a simple "Hi!\""""

    async def callback(self):
        await self.interaction.response.send_message("Hi!")


class HelloUserCommand(discord.app.SlashCommand, name="hello_user"):
    """Say hello to some user"""
    target: discord.User = discord.Option(description="The user to say hello to.")

    async def callback(self):
        await self.interaction.response.send_message(f"{self.target.mention} Hi!")


class HelloCollection(CommandCollection):
    """Commands for saying hello"""

    def __init__(self, bot):
        super().__init__(bot, [HelloCommand, HelloUserCommand])


def setup(bot) -> list:
    return [HelloCollection(bot)]
