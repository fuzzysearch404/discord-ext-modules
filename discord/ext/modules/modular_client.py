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

    def __init__(
        self,
        client,
        commands: list,
        name: str = None,
        description: str = None,
        check_children: bool = True
    ) -> None:
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
            self._wrap_callback_with_check(cmd)

            if check_children:
                for child in self._get_all_children(cmd):
                    self._wrap_callback_with_check(child)

    def _wrap_callback_with_check(self, command) -> None:
        def cmd_with_collection_check(function):
            async def wrapper(cmd):
                try:
                    await discord.utils.maybe_coroutine(self.collection_check, cmd)
                except Exception as ex:
                    return await discord.utils.maybe_coroutine(
                        self.handle_collection_check_error, cmd, ex
                    )

                return await function(cmd)

            return wrapper

        command.callback = cmd_with_collection_check(command.callback)

    def _get_all_children(self, command) -> list:
        children = []

        if command._children_:
            for child in command._children_.values():
                children.append(child)

                if child._children_:
                    children.extend(self._get_all_children(child))

        return children

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
        Used to do some internal cleanup, for example, canceling tasks.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} commands={len(self.commands)}>"


class ModularCommandClientBase:

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.command_collections = {}

        self._module_cache = {}
        self._collections_cache = {}
        self._unloaded_extensions = set()

    def load_extension(self, extension_name: str) -> None:
        """
        Loads a module and sets up its command collections.
        The module should have a function named "setup", that takes a single "client" argument,
        and returns a list of CommandCollection objects.
        Before returning the list of CommandCollection objects, the setup function can
        be used to also do some other initialization.

        Parameters:
            extension_name (str): The name of the module to load with importlib.

        Example usage:
            class MyCommandCollectionOne(CommandCollection):
                ...

            class MyCommandCollectionTwo(CommandCollection):
                ...

            def setup(client) -> list:
                return [MyCommandCollectionOne(client), MyCommandCollectionTwo(client)]

        Raises:
            ModuleSetupException: Raised when the module setup fails.
            ModuleAlreadyLoadedException: Raised when trying to load a module that is
            already loaded.
        """
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
        """
        Unloads a module and its command collections.
        This method does not unload the module itself from the memory,
        but it unloads all of the corresponding command collections.

        Parameters:
            extension_name (str): The name of the module to unload.

        Raises:
            ModuleNotLoadedException: Raised when trying to unload a module that is not loaded.
        """
        if extension_name not in self._module_cache or extension_name in self._unloaded_extensions:
            raise ModuleNotLoadedException(f"Module {extension_name} is not loaded")

        command_collections = self._collections_cache[extension_name]

        for coll in command_collections:
            print("Unloading collection:", coll.name)
            self.unload_command_collection(coll)

        self._unloaded_extensions.add(extension_name)

    def reload_extension(self, extension_name: str) -> None:
        """
        Shortcut for unloading and loading a module.
        This method is equivalent to calling unload_extension and then load_extension.

        Parameters:
            extension_name (str): The name of the module to reload.
        """
        self.unload_extension(extension_name)
        self.load_extension(extension_name)

    def get_command_collection(self, collection_name: str) -> CommandCollection:
        """
        Returns a loaded CommandCollection object by its name. (non case sensitive)

        Parameters:
            collection_name (str): The name of the CommandCollection object to return.

        Raises:
            KeyError: Raised when the collection is not loaded or the name is not found.
        """
        return self.command_collections[collection_name.lower()]

    def load_command_collection(self, collection: CommandCollection) -> None:
        """
        Loads a CommandCollection object into the client and adds the application commands,
        in that particular collection, to the client.

        Parameters:
            collection (CommandCollection): The CommandCollection object to load.

        Raises:
            CommandCollectionAlreadyLoadedException: Raised when trying to load a collection
            that is already loaded.
        """
        collection_name = collection.name.lower()

        if collection_name in self.command_collections:
            raise CollectionAlreadyLoadedException(f"Collection {collection} is already loaded")

        for cmd in collection.commands:
            print(f"Adding {cmd._name_} command")
            self.application_command(cmd)

        self.command_collections[collection_name] = collection

    def unload_command_collection(self, collection: CommandCollection) -> None:
        """
        Unloads a CommandCollection object from the client and removes the application commands,
        in that particular collection, from the client.

        Parameters:
            collection (CommandCollection): The CommandCollection object to unload.

        Raises:
            CommandCollectionNotLoadedException: Raised when trying to unload a collection
            that is not loaded.
        """
        collection_name = collection.name.lower()

        if collection_name not in self.command_collections:
            raise CollectionNotLoadedException(f"Collection {collection} is not loaded")

        collection.on_unload()

        # TODO: Unload commands
        #  for cmd in collection.commands:
        #    pass

        del self.command_collections[collection_name]

    @discord.utils.copy_doc(discord.Client.close)
    async def close(self) -> None:
        for _, collection in tuple(self.command_collections.items()):
            try:
                self.unload_command_collection(collection)
            except Exception:
                pass

        await super().close()


class ModularCommandClient(ModularCommandClientBase, discord.Client):
    """
    Modular command client based on discord.Client.

    Attributes:
        command_collections (dict): A dictionary of currently loaded CommandCollection objects
        by non case sensitive names.
    """
    pass


class AutoShardedModularCommandClient(ModularCommandClientBase, discord.AutoShardedClient):
    """
    Modular command client based on discord.AutoShardedClient.

    Attributes:
        command_collections (dict): A dictionary of currently loaded CommandCollection objects
        by non case sensitive names.
    """
    pass
