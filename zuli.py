import asyncio
import zcs
import smartplug
import sys
from datetime import datetime
from bleak import BleakScanner

TRANSLATION_LAYER = {
    "on": (smartplug.on, lambda a : []),
    "brightness": (smartplug.on, lambda a : [int(a[1])]),
    "off": (smartplug.off, lambda a : []),
    "mode": (smartplug.set_mode, lambda a : [a[1] != "dimmable"]),
    "power": (smartplug.read_power, lambda a : []),
    "time": (smartplug.get_clock, lambda a : []),
    "synctime": (smartplug.sync_clock, lambda a : []),
    "schedule": (smartplug.get_schedule, lambda a : [int(a[1])]),
    "schedules": (smartplug.get_schedule_info, lambda a : [])
}

async def do(args, devices):
    # Use the translation layer to "translate" command line input to a zcs
    # method call with appropriate arguments
    translation = TRANSLATION_LAYER[args[0]]
    command = translation[0]
    command_args = translation[1](args)
    
    print("Firing commands")
    async for response in command(devices, *command_args):
        print(response)
    print("All commands have finished")

async def ainput(prompt: str) -> str:
    await asyncio.to_thread(sys.stdout.write, f'{prompt} ')
    return (await asyncio.to_thread(sys.stdin.readline)).rstrip('\n')

async def command_prompt(devices):
    raw_command = await ainput("Enter command: ")
    args = raw_command.split(" ", maxsplit=1)
    if args[0] != "disconnect":
        await do(args, devices)
        return True
    else:
        return False
    
async def handle_discovered_devices(scanner, devices):
    tasks = set()
    async for (device, advertisement_data) in scanner.advertisement_data():
            if device not in devices:
                print(f"Discovered new device {device.address}")
                devices.append(device)
            if not device.is_connected:
                print(f"{device.address} is disconnected, connecting")
                connect_task = asyncio.create_task(device.connect())
                tasks.add(connect_task)
                connect_task.add_done_callback(tasks.discard)

async def main():
    async with BleakScanner(service_uuids=[zcs.ZULI_SERVICE]) as scanner:
        print("Discovering devices")
        # Keep handle for task so it isn't garbage collected
        global discovery_handler
        devices = []
        discovery_handler = asyncio.create_task(handle_discovered_devices(
            scanner, devices))
        try:
            print("Ready. Devices will continue to connect")
            while await command_prompt(devices):
                # From the docs: "Setting the delay to 0 provides an optimized
                # path to allow other tasks to run"
                await asyncio.sleep(0)
        except Exception as e:
            print(e)
        finally:
            print(f"Closing all connections")
            await asyncio.gather(*[client.disconnect() for client in devices])

asyncio.run(main())