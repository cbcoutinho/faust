"""Tables (changelog stream)."""
from typing import Any, Callable, Mapping
from . import stores
from .streams import Stream
from .types import AppT, Event
from .types.tables import TableT
from .utils.collections import ManagedUserDict

__all__ = ['Table']


class Table(TableT, Stream, ManagedUserDict):
    _store: str

    def __init__(self, *,
                 table_name: str = None,
                 default: Callable[[], Any] = None,
                 store: str = None,
                 **kwargs: Any) -> None:
        self.table_name = table_name
        self.default = default
        self._store = store
        assert not self._coroutines  # Table cannot have generator callback.
        Stream.__init__(self, **kwargs)

    def __hash__(self) -> int:
        # We have to override MutableMapping __hash__, so that this table
        # can be registered in the app._tables mapping.
        return Stream.__hash__(self)

    def __missing__(self, key: Any) -> Any:
        if self.default is not None:
            value = self[key] = self.default()
            return value
        raise KeyError(key)

    def info(self) -> Mapping[str, Any]:
        # Used to recreate object in .clone()
        return {**super().info(), **{
            'table_name': self.table_name,
            'store': self._store,
            'default': self.default,
        }}

    def on_bind(self, app: AppT) -> None:
        if self.StateStore is not None:
            self.data = self.StateStore(url=None, app=app)
        else:
            url = self._store or self.app.store
            self.data = stores.by_url(url)(url, app, loop=self.loop)
        self.changelog_topic = self.derive_topic(self._changelog_topic_name())
        app.add_table(self)

    def on_key_set(self, key: Any, value: Any) -> None:
        self.app.send_soon(self.changelog_topic, key=key, value=value)

    def on_key_del(self, key: Any) -> None:
        self.app.send_soon(self.changelog_topic, key=key, value=None)

    async def on_done(self, value: Event = None) -> None:
        self[value.req.key] = value
        super().on_done(value)  # <-- original value

    def _changelog_topic_name(self) -> str:
        return '{0.app.id}-{0.table_name}-changelog'
