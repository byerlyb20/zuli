import asyncio
from typing import Awaitable, Callable, TypeVar
from . import protocol
from datetime import datetime
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    establish_connection,
    BleakClientWithServiceCache
)

class UnexpectedResponseError(Exception):
    pass

T = TypeVar('T')
EncoderOrMessage = Callable[[BleakClient], Awaitable[bytearray]] | bytearray
Decoder = Callable[[bytearray], T]

def decode_response_success(response: bytearray) -> bool:
    return protocol.decode_response_status(response).is_success()

class ZuliSmartplug():

    def __init__(self, device: BLEDevice):
        self._device: BLEDevice = device
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()

    async def __get_connected_client(self) -> BleakClient:
        if self._client and self._client.is_connected:
            return self._client
        else:
            return await establish_connection(
                BleakClientWithServiceCache,
                self._device,
                self._device.name or self._device.address,
                max_attempts=3
            )
    
    async def _send_command(
        self,
        encode_message: EncoderOrMessage,
        decode_response: Decoder[T] = decode_response_success
    ) -> T:
        async with self._lock:
            client = await self.__get_connected_client()

            # Encode and send message
            message = await encode_message(client) if callable(encode_message) else encode_message
            await client.write_gatt_char(protocol.COMMAND_PIPE, data=message,
                                        response=True)
            
            # Read and decode response
            raw_response = await client.read_gatt_char(protocol.COMMAND_PIPE)
            try:
                return decode_response(raw_response)
            except Exception as e:
                raise UnexpectedResponseError() from e
    
    async def disconnect(self):
        if self._client != None and self._client.is_connected:
            await self._client.disconnect()

    @property
    def address(self):
        return self._device.address
    
    async def on(self, brightness: int):
        return await self._send_command(protocol.encode_on(brightness))

    async def off(self):
        return await self._send_command(protocol.encode_off())
    
    async def read(self):
        return await self._send_command(
            protocol.encode_read(),
            protocol.decode_read
        )
    
    async def get_mode(self):
        return await self._send_command(
            protocol.encode_get_mode(),
            protocol.decode_get_mode
        )

    async def set_mode(self, is_appliance: bool):
        return await self._send_command(protocol.encode_set_mode(is_appliance))

    async def sync_clock(self):
        return await self._send_command(protocol.encode_set_clock(datetime.today()))
    
    async def get_clock(self):
        return await self._send_command(
            protocol.encode_get_clock(),
            protocol.decode_get_clock
        )

    async def read_power(self):
        return await self._send_command(
            protocol.encode_read_power(),
            protocol.decode_read_power
        )
    
    async def add_schedule(self, schedule: protocol.Schedule):
        return await self._send_command(protocol.encode_add_schedule(schedule))

    async def get_schedule(self, i: int):
        return await self._send_command(
            protocol.encode_get_schedule(i),
            protocol.decode_get_schedule
        )

    async def get_schedule_info(self):
        return await self._send_command(
            protocol.encode_get_schedule_info(),
            protocol.decode_get_schedule_info
        )

    async def get_schedules_stream(self):
        schedule_info = await self.get_schedule_info()
        num_schedules = schedule_info['num_schedules']

        for i in range(1, num_schedules + 1):
            yield await self.get_schedule(i)
    
    async def get_schedules(self):
        schedules = [schedule async for schedule in self.get_schedules_stream()]
        return sorted(schedules, key=lambda s: s.id)

    async def remove_schedule(self, i: int):
        schedule = await self.get_schedule(i)
        return await self._send_command(protocol.encode_remove_schedule(schedule))
