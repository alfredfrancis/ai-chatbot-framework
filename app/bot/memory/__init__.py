from collections import OrderedDict
from typing import Text, Optional, List
from app.bot.memory.models import State


class MemorySaver:
    """
    MemorySaver is an abstract class that defines the interface for a memory saver.
    """

    async def init_state(self, thread_id: Text) -> State:
        """
        Initialize a new state for a given thread_id
        """
        return State(thread_id=thread_id)

    async def save(self, thread_id: Text, state: State):
        """
        append the state to the memory for a given thread_id
        """
        raise NotImplementedError("save method not implemented")

    async def get(self, thread_id) -> Optional[State]:
        raise NotImplementedError("get method not implemented")

    async def get_all(self, thread_id) -> List[State]:
        raise NotImplementedError("get_all method not implemented")


class MemorySaverInMemory(MemorySaver):
    def __init__(self):
        self.memory = OrderedDict()

    async def save(self, thread_id: Text, state: State):
        if thread_id not in self.memory:
            self.memory[thread_id] = []
        self.memory[thread_id].append(state)

    async def get(self, thread_id) -> Optional[State]:
        if thread_id not in self.memory:
            return None
        return self.memory.get(thread_id)[-1]

    async def get_all(self, thread_id) -> List[State]:
        if thread_id not in self.memory:
            return []
        return self.memory.get(thread_id)
