import asyncio, datetime, zcs
from bleak import BleakScanner, BleakClient

DISCOVER_DURATION = 4
ZULI_SERVICE = '04ee929b-bb13-4e77-8160-18552daf06e1'
COMMAND_PIPE = 'ffffff03-bb13-4e77-8160-18552daf06e1'

def build_packet(command, args):
    if command == "on":
        # TODO: What if there are no arguments?
        return zcs.on(int(args[0]))
    elif command == "off":
        return zcs.off()
    elif command == "mode":
        return zcs.set_mode(args[0] != "dimmable")
    elif command == "power":
        return zcs.read_power()
    elif command == "time":
        return zcs.get_clock()
    elif command == "synctime":
        now = datetime.datetime.today()
        return zcs.set_clock(now)
    elif command == "write":
        return bytearray.fromhex(args[0])

def parse_packet(command, device, response):
    print(f"{device.address} : {response.hex()}")
    if command == "power":
        power = zcs.parse_read_power(response)
        print(f"\tDevice is consuming {round(power, 2)} watts")
    elif command == "time":
        time = zcs.parse_get_clock(response)
        print(f"\tIt is {time.ctime()}")

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
            print("Ready. Available commands are on|off|mode|power|time|synctime|write")
            while True:
                raw_command = input("Enter command: ")
                args = raw_command.split(" ", maxsplit=1)
                command = args[0]
                if command == "disconnect":
                    break
                packet = build_packet(command, args[1:])
                async def send(client, packet):
                    await client.write_gatt_char(COMMAND_PIPE, data=packet,
                                           response=True)
                    response = await client.read_gatt_char(COMMAND_PIPE)
                    parse_packet(command, client, response)
                await asyncio.gather(*[send(client, packet) for client in
                                       tracked_devices])
        except Exception as e:
            print(e)
        finally:
            print(f"Closing all connections")
            await asyncio.gather(*[client.disconnect() for client in tracked_devices])

asyncio.run(main())