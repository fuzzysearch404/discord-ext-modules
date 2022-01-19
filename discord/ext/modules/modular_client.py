"""
The MIT License (MIT)

Copyright (c) 2022-present fuzzysearch404

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
import discord
import importlib


class ModularCommandClientException(Exception):
    """Base exception class for modular command client errors."""
    pass


class ModuleSetupException(ModularCommandClientException):
    """Raised when a module setup fails."""
    pass


class ModuleAlreadyLoadedException(ModuleSetupException):
    """Raised when trying to load a module that is already loaded."""
    pass


class ModuleNotLoadedException(ModuleSetupException):
    """Raised when trying to unload a module is not loaded."""
    pass


class CollectionSetupException(ModularCommandClientException):
    """Raised when a collection setup fails."""
    pass


class CollectionAlreadyLoadedException(CollectionSetupException):
    """Raised when trying to load a command collection that is already loaded."""
    pass


class CollectionNotLoadedException(CollectionSetupException):
    """Raised when trying to unload a command collection that is not loaded."""
    pass


class CommandCollection:
    """
    Holds a logical collection of commands.

    All of the commands in the collection can have a collection_check function,
    that is called before any command callback in this collection is executed.
    If the collection_check fails, by raising any Exception,
    the command is not executed and handle_collection_check_error is called instead.

    This class should be subclassed to create new command collections.
    """

    def __init__(self, client, commands: list, name: str = None, description: str = None) -> None:
        self.client = client
        self.commands = commands
        self.name = name or self.__class__.__name__
        if description:
            self.description = description
        else:
            doc = self.__doc__
            if doc:
                self.description = doc.strip()
            else:
                self.description = "No description provided."

        # Attach collection_check to each command callback
        for cmd in commands:
            def cmd_with_collection_check(function):
                async def wrapper(command):
                    try:
                        await self.collection_check(command)
                    except Exception as ex:
                        return await self.handle_collection_check_error(command, ex)

                    return await function(command)

                return wrapper

            cmd.callback = cmd_with_collection_check(cmd.callback)

    async def collection_check(self, command) -> None:
        """
        Called before any command callback in this module is executed.
        To fail this check, raise any Exception.
        If this check fails, the command is not executed and handle_collection_check_error
        is called instead.
        """
        ...

    async def handle_collection_check_error(self, command, exception: Exception) -> None:
        """
        Called when collection_check fails.
        By default, this method responds to the interaction with an ephemeral
        message that contains the message of raised exception.
        """
        await command.interaction.response.send_message(str(exception), ephemeral=True)

    def on_unload(self):
        """
        Called when the collection is unloaded.
        Used to do some interal cleanup, for example, canceling tasks.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} commands={len(self.commands)}>"


class ModularCommandClient(discord.Client):
    """
    A modular application command client.

    Attributes:
        command_collections (dict): A dictionary of currently loaded CommandCollection objects
        by name.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_collections = {}

        self._module_cache = {}
        self._collections_cache = {}
        self._unloaded_extensions = set()

    def load_extension(self, extension_name: str) -> None:
        if extension_name not in self._module_cache:
            module = importlib.import_module(extension_name)
        elif extension_name not in self._unloaded_extensions:
            raise ModuleAlreadyLoadedException(f"Module {extension_name} is already loaded")
        else:
            self._unloaded_extensions.remove(extension_name)
            module = self._module_cache[extension_name]
            module = importlib.reload(module)
            self._module_cache[extension_name] = module

        setup_function = getattr(module, "setup", None)
        if not setup_function:
            raise ModuleSetupException(f"Module {module} does not have a setup function")

        try:
            command_collections = setup_function(self)
        except Exception as e:
            raise ModuleSetupException(f"Module {module} setup function raised: {e}")

        for coll in command_collections:
            print("Loading collection:", coll.name)
            self.load_command_collection(coll)

        self._module_cache[extension_name] = module
        self._collections_cache[extension_name] = command_collections

    def unload_extension(self, extension_name: str) -> None:
        if extension_name not in self._module_cache or extension_name in self._unloaded_extensions:
            raise ModuleNotLoadedException(f"Module {extension_name} is not loaded")

        command_collections = self._collections_cache[extension_name]

        for coll in command_collections:
            print("Unloading collection:", coll.name)
            self.unload_command_collection(coll)

        self._unloaded_extensions.add(extension_name)

    def reload_extension(self, extension_name: str) -> None:
        self.unload_extension(extension_name)
        self.load_extension(extension_name)

    def get_command_collection(self, collection_name: str) -> CommandCollection:
        return self.command_collections[collection_name]

    def load_command_collection(self, collection: CommandCollection) -> None:
        collection_name = collection.__class__.__name__

        if collection_name in self.command_collections:
            raise CollectionAlreadyLoadedException(f"Collection {collection} is already loaded")

        for cmd in collection.commands:
            print(f"Adding {cmd._name_} command")
            self.application_command(cmd)

        self.command_collections[collection_name] = collection

    def unload_command_collection(self, collection: CommandCollection) -> None:
        collection_name = collection.__class__.__name__

        if collection_name not in self.command_collections:
            raise CollectionNotLoadedException(f"Collection {collection} is not loaded")

        collection.on_unload()

        # TODO: Unload commands
        #  for cmd in collection.commands:
        #    pass

        del self.command_collections[collection_name]
