import asyncio
import zcs
import smartplug
import sys
from datetime import time
from bleak import BleakScanner
from bleak import BleakClient

def get_schedules(clients):
    for client in clients:
        return smartplug.get_client_schedules(client)
    
def remove_schedule(clients, i):
    for client in clients:
        return smartplug.remove_client_schedule(client, i)

TRANSLATION_LAYER = {
    "on": (smartplug.on, lambda a : []),
    "brightness": (smartplug.on, lambda a : [int(a[1])]),
    "off": (smartplug.off, lambda a : []),
    "mode": (smartplug.set_mode, lambda a : [a[1] != "dimmable"]),
    "power": (smartplug.read_power, lambda a : []),
    "time": (smartplug.get_clock, lambda a : []),
    "synctime": (smartplug.sync_clock, lambda a : []),
    "schedules": (get_schedules, lambda a : []),
    "remove_schedule": (remove_schedule, lambda a : [int(a[1])]),
    "add_schedule": (smartplug.add_schedule,
                     lambda a : [zcs.Schedule(time=time.fromisoformat(a[1]),
                                              action=zcs.Schedule.ACTION_OFF
                                              if a[2] == "off"
                                              else zcs.Schedule.ACTION_ON)]),
    "write": (smartplug.send_commands, lambda a : [bytearray.fromhex(a[1])])
}

async def do(args, devices):
    # Use the translation layer to "translate" command line input to a zcs
    # method call with appropriate arguments
    translation = TRANSLATION_LAYER[args[0]]
    command = translation[0]
    command_args = translation[1](args)
    
    async for response in command(devices, *command_args):
        if isinstance(response, bytearray):
            print(response.hex())
        else:
            print(response)

async def ainput(prompt: str) -> str:
    print(f"{prompt} ", end='', flush=True)
    return (await asyncio.to_thread(sys.stdin.readline)).rstrip('\n')

async def command_prompt(devices):
    raw_command = await ainput(f"Enter command: ")
    args = raw_command.split(" ")
    if args[0] != "disconnect":
        await do(args, devices)
        return True
    else:
        return False

async def main():
    devices = {}
    async with BleakScanner(service_uuids=[zcs.ZULI_SERVICE]) as scanner:
        print("Approach a device. Waiting to connect")
        async for (device, advertisement_data) in scanner.advertisement_data():
            if advertisement_data.rssi > -70:
                client = BleakClient(device)
                devices[device.address] = client
                await client.connect()
                print(f"Connected to {device.address}")
                break
    try:
        print("Ready.")
        while await command_prompt(devices.values()):
            # From the docs: "Setting the delay to 0 provides an optimized
            # path to allow other tasks to run"
            await asyncio.sleep(0)
    except Exception as e:
        print(e)
    finally:
        print(f"Closing all connections")
        await asyncio.gather(*[client.disconnect()
                                for client in devices.values()])

asyncio.run(main())