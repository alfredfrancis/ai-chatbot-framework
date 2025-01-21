from collections import OrderedDict
from typing import Text, Optional, List
from app.bot.memory.models import State
from app.bot.dialogue_manager.models import UserMessage


class MemorySaver:
    """
    MemorySaver is an abstract class that defines the interface for a memory saver.
    """

    def init_state(self, thread_id: Text, user_message: UserMessage) -> State:
        """
        Initialize a new state for a given thread_id
        """
        return State(thread_id=thread_id, user_message=user_message)

    def save(self, thread_id: Text, state: State):
        """
        append the state to the memory for a given thread_id
        """
        raise NotImplementedError("save method not implemented")

    def get(self, thread_id) -> Optional[State]:
        raise NotImplementedError("get method not implemented")

    def get_all(self, thread_id) -> List[State]:
        raise NotImplementedError("get_all method not implemented")

    def delete(self, thread_id):
        raise NotImplementedError("delete method not implemented")


class MemorySaverInMemory(MemorySaver):
    def __init__(self):
        self.memory = OrderedDict()

    def save(self, thread_id: Text, state: State):
        if thread_id not in self.memory:
            self.memory[thread_id] = []
        self.memory[thread_id].append(state)

    def get(self, thread_id) -> Optional[State]:
        if thread_id not in self.memory:
            return None
        return self.memory.get(thread_id)[-1]

    def get_all(self, thread_id) -> List[State]:
        if thread_id not in self.memory:
            return []
        return self.memory.get(thread_id)

    def delete(self, thread_id):
        if thread_id not in self.memory:
            return
        del self.memory[thread_id]
