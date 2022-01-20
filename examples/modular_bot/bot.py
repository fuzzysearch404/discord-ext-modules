import discord
from discord.ext.modules import ModularCommandClient


if __name__ == "__main__":
    client = ModularCommandClient(intents=discord.Intents.none())

    @client.event
    async def on_ready():
        print("Logged on as {0}!".format(client.user))

    client.load_extension("commands.hello_module")
    client.load_extension("commands.advanced_module")
    client.run("your_bot_token")
