import asyncio
import zcs
import smartplug
import sys
import argparse
from datetime import time
from bleak import BleakScanner
from bleak import BleakClient

def get_schedules(clients):
    for client in clients:
        return smartplug.get_client_schedules(client)
    
def remove_schedule(clients, i):
    for client in clients:
        return smartplug.remove_client_schedule(client, i)
    
async def get_devices(clients):
    for client in clients:
        yield client.address

async def ainput(prompt: str) -> str:
    print(f"{prompt} ", end='', flush=True)
    return (await asyncio.to_thread(sys.stdin.readline)).rstrip('\n')
    
def configure_parser():
    parser = argparse.ArgumentParser(prog="zuli", exit_on_error=False)
    subparsers = parser.add_subparsers(title="command", required=True)

    parser_on = subparsers.add_parser('on')
    parser_on.add_argument('brightness', nargs='?', default=0, type=int)
    parser_on.set_defaults(func=smartplug.on,
                            params=lambda a : [a.brightness])

    parser_off = subparsers.add_parser('off')
    parser_off.set_defaults(func=smartplug.off)

    parser_mode = subparsers.add_parser('mode')
    parser_mode.add_argument('mode', choices=['dimmable', 'appliance'])
    parser_mode.set_defaults(func=smartplug.set_mode,
                                params=lambda a : [a.mode == 'appliance'])
    
    parser_power = subparsers.add_parser('power')
    parser_power.set_defaults(func=smartplug.read_power)

    parser_time = subparsers.add_parser('time')
    parser_time.set_defaults(func=smartplug.get_clock)

    parser_synctime = subparsers.add_parser('synctime')
    parser_synctime.set_defaults(func=smartplug.sync_clock)

    parser_schedule = subparsers.add_parser('schedules')
    parser_schedule.set_defaults(func=get_schedules)

    parser_schedule_remove = subparsers.add_parser('remove_schedule')
    parser_schedule_remove.add_argument('schedule', type=int)
    parser_schedule_remove.set_defaults(func=remove_schedule,
                                        params=lambda a : [a.schedule])
    
    parser_schedule_add = subparsers.add_parser('add_schedule')
    parser_schedule_add.add_argument('time', type=time.fromisoformat)
    parser_schedule_add.add_argument('action', choices=['on', 'off'])
    def schedule_params(a):
        return [zcs.Schedule(time=a.time, action=zcs.Schedule.ACTION_OFF
                                            if a.action == "off"
                                            else zcs.Schedule.ACTION_ON)]
    parser_schedule_add.set_defaults(func=smartplug.add_schedule,
                                        params=schedule_params)
    
    parser_devices = subparsers.add_parser('devices')
    parser_devices.set_defaults(func=get_devices)

    subparsers.add_parser('quit')

    return parser

async def main():
    devices = {}
    async def discover():
        async with BleakScanner(service_uuids=[zcs.ZULI_SERVICE]) as scanner:
            async for (device, advertisement_data) in scanner.advertisement_data():
                if device.address not in devices:
                    client = BleakClient(device)
                    await client.connect()
                    devices[device.address] = client
    asyncio.create_task(discover())
    try:
        print("Ready. Devices will continue to connect in the background")
        parser = configure_parser()

        while True:
            command = await ainput(">>>")
            if command.startswith("quit"):
                break
            try:
                args = parser.parse_args(command.split())
            except Exception as e:
                print(e)
                continue
            params = args.params(args) if hasattr(args, 'params') else []
            async for result in args.func(devices.values(), *params):
                if isinstance(result, bytearray):
                    print(result.hex())
                else:
                    print(result)
    except argparse.ArgumentError as e:
        print(e)
    finally:
        print(f"Closing all connections")
        await asyncio.gather(*[client.disconnect()
                                for client in devices.values()])

asyncio.run(main())