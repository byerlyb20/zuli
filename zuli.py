import asyncio, datetime
from bleak import BleakScanner, BleakClient

class Operation:
    def __init__(self, id, does_read=False):
        self.id = id
        self.does_read = does_read

ZULI_SERVICE = '04ee929b-bb13-4e77-8160-18552daf06e1'
COMMAND_PIPE = 'ffffff03-bb13-4e77-8160-18552daf06e1'
PIPE_OPERATIONS = {
    "on" : Operation(b'\x17'),
    "off" : Operation(b'\x18'),
    "mode" : Operation(b'\x10'),
    "power" : Operation(b'\x20', does_read=True),
    "time" : Operation(b'\x09', does_read=True),
    "synctime" : Operation(b'\x08')
}

def build_pipe_operation(command, args):
    data = bytearray(PIPE_OPERATIONS[command].id)
    if command == "on":
        brightness = 100
        if len(args) > 0:
            brightness = min(100, max(1, int(args[0])))
        data.extend(b'\x00\x00\x00\x00')
        data.extend(brightness.to_bytes(1))
        data.extend(b'\x00\x00\x00')
    elif command == "off":
        data.extend(b'\x00\x00\x00')
    elif command == "mode":
        mode = 0
        if len(args) > 0:
            mode = min(1, max(0, int(args[0])))
        data.extend(mode.to_bytes(1))
    elif command == "synctime":
        now = datetime.datetime.today()
        data.extend(now.year.to_bytes(2))
        data.extend(bytearray([now.month, now.day, (now.weekday() + 2) % 7, now.hour, now.minute, now.second]))
    return data

def read_pipe_operation(command, device, response):
    if command == "power":
        power = int.from_bytes(response) / 1e20
        print(f"{device.address} is consuming {round(power, 2)} watts")
    elif command == "time":
        year = int.from_bytes(response[1:3])
        time = datetime.datetime(year, month=response[3], day=response[4], hour=response[6], minute=response[7], second=response[8])
        print(f"It is {time.ctime()} at {device.address}")

async def main():
    async with BleakScanner() as scanner:
        print("Discovering devices")
        await asyncio.sleep(4)

    tracked_devices = []
    for (device, advertising_data) in scanner.discovered_devices_and_advertisement_data.values():
        if ZULI_SERVICE in advertising_data.service_uuids:
            tracked_devices.append(BleakClient(device))
    
    print(f"Connecting {len(tracked_devices)} device(s)")
    if len(tracked_devices) > 0:
        try:
            await asyncio.gather(*[client.connect() for client in tracked_devices])
            print("Ready. Available commands are ", '|'.join(PIPE_OPERATIONS), "|read|write", sep='')
            while True:
                raw_command = input("Enter command: ")
                args = raw_command.split(" ", maxsplit=1)
                command = args[0]
                if command in PIPE_OPERATIONS:
                    data = build_pipe_operation(command, args[1:])
                    await asyncio.gather(*[client.write_gatt_char(COMMAND_PIPE, data=data, response=True) for client in tracked_devices])
                    if PIPE_OPERATIONS[command].does_read:
                        async def read(client):
                            response = await client.read_gatt_char(COMMAND_PIPE)
                            read_pipe_operation(command, client, response[1:])
                        await asyncio.gather(*[read(client) for client in tracked_devices])
                elif command == "write" or command == "read":
                    if len(args) > 1:
                        data = bytearray.fromhex(args[1])
                        await asyncio.gather(*[client.write_gatt_char(COMMAND_PIPE, data=data, response=True) for client in tracked_devices])
                        if command == "read":
                            async def read(client):
                                response = await client.read_gatt_char(COMMAND_PIPE)
                                print(f"{client.address} : {response.hex()}")
                            await asyncio.gather(*[read(client) for client in tracked_devices])
                elif command == "disconnect":
                    break
        except Exception as e:
            print(e)
        finally:
            print(f"Closing all connections")
            await asyncio.gather(*[client.disconnect() for client in tracked_devices])

asyncio.run(main())