import zcs
import asyncio
from datetime import datetime
from bleak import BleakClient
from typing import Tuple
from typing import AsyncGenerator

class ResponseMismatchError(Exception):
    pass

class SmartplugBusyError(Exception):
    pass

class MalformedCommandError(Exception):
    pass

async def send_command(client, packet: bytearray):
    await client.write_gatt_char(zcs.COMMAND_PIPE, data=packet,
                                        response=True)
    return await client.read_gatt_char(zcs.COMMAND_PIPE)

async def send_commands(clients,
                        packet: bytearray) -> AsyncGenerator[bytearray, None]:
    response_queue = asyncio.Queue()
    tasks = set()
    for client in clients:
        task = asyncio.create_task(send_command(client, packet))
        tasks.add(task)
        task.add_done_callback(
            lambda task : response_queue.put_nowait(task.result())
        )
        task.add_done_callback(tasks.discard)
    for i in range(len(clients)):
        yield await response_queue.get()

async def send_commands_deaf(clients, packet: bytearray):
    await asyncio.gather(*[send_command(client, packet) for client in clients])

def on(clients, brightness=0):
    return send_commands(clients, zcs.on(brightness))

def off(clients):
    return send_commands(clients, zcs.off())

def set_mode(clients, is_appliance = True):
    return send_commands(clients, zcs.set_mode(is_appliance))

def sync_clock(clients):
    return send_commands(clients, zcs.set_clock(datetime.today()))

async def get_clock(clients) -> AsyncGenerator[datetime, None]:
    async for response in send_commands(clients, zcs.get_clock()):
        yield zcs.parse_get_clock(response)

async def read_power(clients) -> AsyncGenerator[int, None]:
    async for response in send_commands(clients, zcs.read_power()):
        yield zcs.parse_read_power(response)

def add_schedule(clients, schedule: zcs.Schedule):
    return send_commands(clients, zcs.add_schedule(schedule))

async def get_schedule(client, i: int):
    return zcs.parse_get_schedule(await send_command(client,
                                                     zcs.get_schedule(i)))

async def get_client_schedule_info(client):
    return zcs.parse_get_schedule_info(await send_command(client,
                                                   zcs.get_schedule_info()))

async def get_client_schedules(client):
    schedule_info = await get_client_schedule_info(client)
    num_schedules = schedule_info[0]
    for i in range(1, num_schedules + 1):
        yield await get_schedule(client, i)

async def remove_client_schedule(client, i: int):
    schedule = await get_schedule(client, i)
    yield await send_command(client, zcs.remove_schedule(schedule))