"""WebSocket client for Helios easyControls 3.0."""

from __future__ import annotations

import asyncio
import logging
import struct
from typing import Sequence

from websockets.asyncio.client import connect

from .addresses import (
    WS_CMD_READ_DATA,
    WS_CMD_READ_TABLES,
    WS_CMD_WRITE_DATA,
    WS_REPLY_ACK,
)
from .const import DEFAULT_PORT, DEFAULT_REQUEST_TIMEOUT_SECONDS

LOGGER = logging.getLogger(__name__)


class EasyControlsProtocolError(Exception):
    """Error in the protocol layer or response parsing."""


def _build_frame(command: int, payload: Sequence[int]) -> bytes:
    """
    Build a complete frame.

    Format (Uint16 LE): [length=N-1][command][payload...][checksum]
    Checksum = sum(all preceding words) & 0xFFFF
    """
    total_words = 1 + 1 + len(payload) + 1   # length + cmd + payload + csum
    length = total_words - 1
    words = [length & 0xFFFF, command & 0xFFFF, *(int(p) & 0xFFFF for p in payload)]
    checksum = sum(words) & 0xFFFF
    words.append(checksum)
    return struct.pack(f"<{len(words)}H", *words)


def _parse_words(raw: bytes) -> tuple[int, ...]:
    """Convert bytes to Uint16-LE tuple."""
    if len(raw) % 2 != 0:
        raise EasyControlsProtocolError(f"Response length {len(raw)} not even")
    return struct.unpack(f"<{len(raw)//2}H", raw)


def _verify_checksum(words: Sequence[int]) -> bool:
    """Check whether the last word equals the sum of preceding words."""
    if len(words) < 2:
        return False
    return (sum(words[:-1]) & 0xFFFF) == words[-1]


class EasyControls3Client:
    """
    Async WebSocket client for a single KWL.

    Thread-safe via asyncio.Lock — only one WS connection per instance at a
    time. Connection is opened/closed per request because the device doesn't
    handle long-lived connections well.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT,
                 timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS):
        self._url = f"ws://{host}:{port}/"
        self._lock = asyncio.Lock()
        self._timeout = timeout

    @property
    def url(self) -> str:
        return self._url

    async def _exchange(self, request: bytes) -> bytes:
        """Send a frame and read exactly one response."""
        async with self._lock:
            async with connect(self._url, open_timeout=self._timeout,
                               close_timeout=self._timeout) as ws:
                await asyncio.wait_for(ws.send(request), timeout=self._timeout)
                return await asyncio.wait_for(ws.recv(), timeout=self._timeout)

    # --- High level: Table 0 (~ first 250 variables at once) ----------------

    async def read_table(self, table_id: int = 0) -> bytes:
        """
        Read a complete table. Table 0 = standard data block.
        Response = raw buffer (bytes); fixed byte offsets per device layout.
        """
        request = _build_frame(WS_CMD_READ_TABLES, [table_id])
        return await self._exchange(request)

    # --- Low level: individual variables ------------------------------------

    async def read_variables(self, addresses: Sequence[int]) -> dict[int, int]:
        """
        Read 1..n variables via READ_DATA.

        Returns dict {addr: value}. Raises EasyControlsProtocolError on errors.
        Response format: [len][cmd_echo=0xF9][addr_echo][value][...][csum]
        For batch: 2 words per item (addr_echo, value) in the same order.
        """
        if not addresses:
            return {}
        request = _build_frame(WS_CMD_READ_DATA, addresses)
        raw = await self._exchange(request)
        words = _parse_words(raw)
        if not _verify_checksum(words):
            raise EasyControlsProtocolError(
                f"Checksum error in READ_DATA response: {words}"
            )
        # Body: pairs of (addr_echo, value), no header words
        body = words[2:-1] if len(words) >= 3 else ()
        result = {}
        for i, addr in enumerate(addresses):
            v_idx = 2 * i + 1
            if v_idx < len(body):
                result[addr] = body[v_idx]
        if len(result) != len(addresses):
            LOGGER.warning(
                "READ_DATA: %d addresses requested, %d values returned",
                len(addresses), len(result),
            )
        return result

    async def write_variables(self, items: Sequence[tuple[int, int]]) -> None:
        """
        Write 1..n variables via WRITE_DATA.

        items: list of (address, value) tuples.
        Raises EasyControlsProtocolError if the device doesn't ACK.
        """
        if not items:
            return
        payload: list[int] = []
        for addr, val in items:
            payload.append(int(addr) & 0xFFFF)
            payload.append(int(val) & 0xFFFF)
        request = _build_frame(WS_CMD_WRITE_DATA, payload)
        raw = await self._exchange(request)
        words = _parse_words(raw)
        # Expected ACK: [2][245][247] = "0200 F500 F700"
        if len(words) >= 2 and words[1] == WS_REPLY_ACK:
            return
        raise EasyControlsProtocolError(
            f"Write not acknowledged — response: {[hex(w) for w in words]}"
        )

    # --- Convenience --------------------------------------------------------

    async def read_variable(self, address: int) -> int | None:
        """Convenience single-variable variant."""
        result = await self.read_variables([address])
        return result.get(address)

    async def write_variable(self, address: int, value: int) -> None:
        """Convenience single-variable variant."""
        await self.write_variables([(address, value)])

    async def test_connection(self) -> bool:
        """Connectivity test: read Table 0."""
        try:
            buf = await self.read_table(0)
            return len(buf) > 100
        except Exception as err:
            LOGGER.debug("test_connection failed: %s", err)
            return False
