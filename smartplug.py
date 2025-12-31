from typing import Awaitable, Callable, Optional, TypeVar
import protocol
import asyncio
from datetime import datetime
from bleak import BleakClient
from collections.abc import AsyncGenerator

class ResponseMismatchError(Exception):
    pass

class SmartplugBusyError(Exception):
    pass

class MalformedCommandError(Exception):
    pass

T = TypeVar('T')

def decode_response_success(response: bytearray | None) -> bool:
    if response == None:
        return False
    else:
        return protocol.decode_response_status(response).is_success()

def decode_nullable_response_wrapper(decode_fun: Callable[[bytearray], T]) -> Callable[[bytearray | None], Optional[T]]:
    def decode_nullable_response(response: bytearray | None) -> Optional[T]:
        if response == None:
            return None
        else:
            return decode_fun(response)
    return decode_nullable_response

async def _send_command(client: BleakClient,
                        encode_message: Callable[[BleakClient], Awaitable[bytearray | None]] | bytearray,
                        decode_response: Callable[[bytearray | None], T] = decode_response_success
                        ) -> T:
    message = await encode_message(client) if callable(encode_message) else encode_message
    if message == None:
        return decode_response(None)
    await client.write_gatt_char(protocol.COMMAND_PIPE, data=message,
                                 response=True)
    raw_response = await client.read_gatt_char(protocol.COMMAND_PIPE)
    return decode_response(raw_response)

async def _send_commands(clients: list[BleakClient],
                        encode_message: Callable[[BleakClient], Awaitable[bytearray]] | bytearray,
                        decode_response: Callable[[bytearray | None], T] = decode_response_success
                        ) -> AsyncGenerator[tuple[BleakClient, T]]:
    response_queue = asyncio.Queue()
    tasks = set()
    for client in clients:
        task = asyncio.create_task(_send_command(client, encode_message, decode_response))
        tasks.add(task)
        def done_callback(task, c=client):
            try:
                response_queue.put_nowait((c, task.result()))
            except Exception:
                # Ignore exceptions
                response_queue.put_nowait((c, decode_response(None)))
        task.add_done_callback(done_callback)
    for i in range(len(clients)):
        yield await response_queue.get()

def on(clients: list[BleakClient], brightness=0):
    return _send_commands(clients, protocol.encode_on(brightness))

def off(clients: list[BleakClient]):
    return _send_commands(clients, protocol.encode_off())

def set_mode(clients: list[BleakClient], is_appliance = True):
    return _send_commands(clients, protocol.encode_set_mode(is_appliance))

def sync_clock(clients: list[BleakClient]):
    return _send_commands(clients, protocol.encode_set_clock(datetime.today()))

def get_clock(clients: list[BleakClient]):
    return _send_commands(clients,
                          protocol.encode_get_clock(),
                          decode_nullable_response_wrapper(protocol.decode_get_clock))

def read_power(clients: list[BleakClient]):
    return _send_commands(clients,
                          protocol.encode_read_power(),
                          decode_nullable_response_wrapper(protocol.decode_read_power))

def add_schedule(clients: list[BleakClient], schedule: protocol.Schedule):
    return _send_commands(clients, protocol.encode_add_schedule(schedule))

async def get_schedule(client: BleakClient, i: int):
    return await _send_command(client,
                         protocol.encode_get_schedule(i),
                         decode_nullable_response_wrapper(protocol.decode_get_schedule))

async def get_client_schedule_info(client: BleakClient):
    return await _send_command(client,
                               protocol.encode_get_schedule_info(),
                               decode_nullable_response_wrapper(protocol.decode_get_schedule_info))

async def get_client_schedules(client: BleakClient):
    schedule_info = await get_client_schedule_info(client)
    num_schedules = schedule_info['num_schedules'] if schedule_info != None else 0
    for i in range(1, num_schedules + 1):
        yield await get_schedule(client, i)

async def remove_client_schedule(clients: list[BleakClient], i: int):
    async def encode_remove_ith_schedule(client: BleakClient) -> bytearray | None:
        schedule = await get_schedule(client, i)
        if schedule == None:
            return None
        else:
            return protocol.encode_remove_schedule(schedule)
    yield await _send_command(clients[0], encode_remove_ith_schedule)
