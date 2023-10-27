import asyncio
import zcs
import smartplug
import sys
from bleak import BleakScanner
from bleak import BleakClient

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
    
    async for response in command(devices, *command_args):
        print(response)

async def ainput(prompt: str) -> str:
    print(f"{prompt} ", end='', flush=True)
    return (await asyncio.to_thread(sys.stdin.readline)).rstrip('\n')

async def command_prompt(devices):
    global num
    num += 1
    raw_command = await ainput(f"Enter command: ")
    args = raw_command.split(" ", maxsplit=1)
    if args[0] != "disconnect":
        await do(args, devices)
        return True
    else:
        return False

async def main():
    devices = {}
    async with BleakScanner(service_uuids=[zcs.ZULI_SERVICE]) as scanner:
        print("Waiting for first device to connect")
        async for (device, advertisement_data) in scanner.advertisement_data():
            client = BleakClient(device)
            devices[device.address] = client
            await client.connect()
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