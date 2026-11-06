from __future__ import annotations

import asyncio

import pytest

from src.utils.keyed_locks import KeyedLockPool


@pytest.mark.asyncio
async def test_keyed_lock_serializes_same_key_and_releases_entry() -> None:
    pool = KeyedLockPool()
    active = 0
    maximum_active = 0

    async def task() -> None:
        nonlocal active, maximum_active
        async with pool.hold("same"):
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0)
            active -= 1

    await asyncio.gather(*(task() for _ in range(20)))

    assert maximum_active == 1
    assert pool.active_keys == 0


@pytest.mark.asyncio
async def test_keyed_lock_keeps_waiting_users_on_same_entry() -> None:
    pool = KeyedLockPool()
    entered = asyncio.Event()
    release = asyncio.Event()
    order: list[int] = []

    async def first() -> None:
        async with pool.hold("ticket"):
            entered.set()
            await release.wait()
            order.append(1)

    async def second() -> None:
        await entered.wait()
        async with pool.hold("ticket"):
            order.append(2)

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())
    await entered.wait()
    await asyncio.sleep(0)
    assert pool.active_keys == 1
    release.set()
    await asyncio.gather(first_task, second_task)

    assert order == [1, 2]
    assert pool.active_keys == 0
