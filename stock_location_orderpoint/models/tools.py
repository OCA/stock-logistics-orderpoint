# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import contextvars


class MovesTouchTracker:
    """
    Context manager to track stock moves that are created or updated during its execution.

    This is useful for the stock location orderpoint module to determine which moves were
    affected by the orderpoint processing, allowing it to post-process those moves after
    their creation or update.
    """

    _current_move_ids = contextvars.ContextVar("current_touched_move_ids", default=None)

    def __enter__(self):
        self._token = self._current_move_ids.set(set())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._current_move_ids.reset(self._token)

    @classmethod
    def add_ids(cls, ids):
        current_moves = cls._current_move_ids.get()
        if current_moves is not None:
            current_moves.update(ids)

    @classmethod
    def get_ids(cls):
        return cls._current_move_ids.get()
