import asyncio, zcs
from datetime import datetime
from bleak import BleakScanner, BleakClient

DISCOVER_DURATION = 4
ZULI_SERVICE = '04ee929b-bb13-4e77-8160-18552daf06e1'
COMMAND_PIPE = 'ffffff03-bb13-4e77-8160-18552daf06e1'

TRANSLATION_LAYER = {
    "on": (zcs.on, lambda a : []),
    "brightness": (zcs.on, lambda a : [int(a[1])]),
    "off": (zcs.off, lambda a : []),
    "mode": (zcs.set_mode, lambda a : [a[1] != "dimmable"]),
    "power": (zcs.read_power, lambda a : [], zcs.parse_read_power),
    "time": (zcs.get_clock, lambda a : [], zcs.parse_get_clock),
    "synctime": (zcs.set_clock, lambda a : [datetime.today()]),
    "schedule": (zcs.get_schedule, lambda a : [int(a[1])], zcs.parse_get_schedule),
    "schedules": (zcs.get_schedule_info, lambda a : [], zcs.parse_get_schedule_info),
    "write": (lambda a : a, lambda a : [bytearray.fromhex(a[1])])
}

async def do(args, device):
    # Use the translation layer to "translate" command line input to a zcs
    # method call with appropriate arguments
    translation = TRANSLATION_LAYER[args[0]]
    packet = translation[0](*translation[1](args))

    # Write to and then read from the smartplug
    await device.write_gatt_char(COMMAND_PIPE, data=packet, response=True)
    raw = await device.read_gatt_char(COMMAND_PIPE)

    # Always print out the raw response
    print(f"{device.address} : {raw.hex()}")

    # Print error number (if any) and the zcs parsed response
    status = zcs.parse_response(raw)
    if status[1] != zcs.STATUS_SUCCESS:
        print(f"\tDevice reported error {status[1]}")
    elif len(translation) == 3:
        print(f"\t{translation[2](raw)}")

async def main():
    async with BleakScanner() as scanner:
        print("Discovering devices")
        await asyncio.sleep(DISCOVER_DURATION)

    tracked_devices = []
    for (device, advertising_data) in scanner.discovered_devices_and_advertisement_data.values():
        if ZULI_SERVICE in advertising_data.service_uuids:
            tracked_devices.append(BleakClient(device))
    
    print(f"Connecting {len(tracked_devices)} device(s)")
    if len(tracked_devices) > 0:
        try:
            await asyncio.gather(*[client.connect() for client in tracked_devices])
            print("Ready. Available commands are on|off|mode|power|time|synctime|schedule|schedules|write")
            while True:
                raw_command = input("Enter command: ")
                args = raw_command.split(" ", maxsplit=1)
                if args[0] == "disconnect":
                    break
                else:
                    await asyncio.gather(*[do(args, client) for client in tracked_devices])
        except Exception as e:
            print(e)
        finally:
            print(f"Closing all connections")
            await asyncio.gather(*[client.disconnect() for client in tracked_devices])

asyncio.run(main())