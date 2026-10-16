"""Immutable request snapshots; separate requests and processes never share mutable role state."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from namoz_bot.application.roles.ports import RoleCatalogStore


class RoleCatalogRuntime:
    def __init__(self, store: RoleCatalogStore) -> None:
        self.store, self.roles = store, store.roles

    @asynccontextmanager
    async def scope(self, *, fresh: bool = False) -> AsyncIterator[None]:
        if self.roles.scoped and not fresh:
            yield
        else:
            snapshot = await self.store.load()
            with self.roles.bind(snapshot):
                yield
