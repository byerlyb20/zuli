import asyncio
import zcs
import smartplug
import sys
import argparse
import argparsei
from datetime import time
from bleak import BleakScanner
from bleak import BleakClient

def filter_devices(devices: dict[str, BleakClient], addresses: list[str]):
    # An empty list of addresses returns all devices
    if len(addresses) == 0:
        return list(devices.values())
    
    # Find devices in dict with (possible) partial addresses
    # Performance is not great, but the number of devices should always be very
    # low
    filtered = []
    for addr in addresses:
        for k, v in devices.items():
            if k.startswith(addr):
                filtered.append(v)
    return filtered
    
def wrap_method(smartplug_func):
    """Because methods in the smartplug module do not understand command line
    arguments from argparse.Namespace objects, this method creates and returns
    a wrapper method that reads command line arguments and then calls a
    specified method in the smartplug module."""
    async def do(args: argparse.Namespace, devices: dict[str, BleakClient]):
        command_devices = filter_devices(devices, args.devices)
        method_params = args.params(args) if hasattr(args, 'params') else []
        async for result in smartplug_func(command_devices, *method_params):
            if isinstance(result, bytearray):
                print(result.hex())
            else:
                print(result)
    return do
    
async def list_devices(args: argparse.Namespace,
                       devices: dict[str, BleakClient]):
    for client in devices.values():
        print(client.address)

async def ainput(prompt: str) -> str:
    print(f"{prompt} ", end='', flush=True)
    return (await asyncio.to_thread(sys.stdin.readline)).rstrip('\n')
    
def configure_parser():
    parser = argparsei.InteractiveArgumentParser(prog="zuli", exit_on_error=False)
    subparsers = parser.add_subparsers()

    parent_parser = argparsei.InteractiveArgumentParser(add_help=False)
    parent_parser.add_argument('-d', '--devices', action='extend', nargs='*',
                               type=str, default=[])

    parser_on = subparsers.add_parser('on', parents=[parent_parser])
    parser_on.add_argument('brightness', nargs='?', default=0, type=int)
    parser_on.set_defaults(func=wrap_method(smartplug.on),
                            params=lambda a : [a.brightness])

    parser_off = subparsers.add_parser('off', parents=[parent_parser])
    parser_off.set_defaults(func=wrap_method(smartplug.off))

    parser_mode = subparsers.add_parser('mode', parents=[parent_parser])
    parser_mode.add_argument('mode', choices=['dimmable', 'appliance'])
    parser_mode.set_defaults(func=wrap_method(smartplug.set_mode),
                                params=lambda a : [a.mode == 'appliance'])
    
    parser_power = subparsers.add_parser('power', parents=[parent_parser])
    parser_power.set_defaults(func=wrap_method(smartplug.read_power))

    parser_time = subparsers.add_parser('time', parents=[parent_parser])
    parser_time.set_defaults(func=wrap_method(smartplug.get_clock))

    parser_synctime = subparsers.add_parser('synctime',
                                            parents=[parent_parser])
    parser_synctime.set_defaults(func=wrap_method(smartplug.sync_clock))

    parser_schedule = subparsers.add_parser('schedules',
                                            parents=[parent_parser])
    parser_schedule.set_defaults(func=wrap_method(smartplug.get_client_schedules))

    parser_schedule_remove = subparsers.add_parser('remove_schedule',
                                                   parents=[parent_parser])
    parser_schedule_remove.add_argument('schedule', type=int)
    parser_schedule_remove.set_defaults(func=wrap_method(smartplug.remove_client_schedule),
                                        params=lambda a : [a.schedule])
    
    parser_schedule_add = subparsers.add_parser('add_schedule',
                                                parents=[parent_parser])
    parser_schedule_add.add_argument('time', type=time.fromisoformat)
    parser_schedule_add.add_argument('action', choices=['on', 'off'])
    def schedule_params(a):
        return [zcs.Schedule(time=a.time, action=zcs.Schedule.ACTION_OFF
                                            if a.action == "off"
                                            else zcs.Schedule.ACTION_ON)]
    parser_schedule_add.set_defaults(func=smartplug.add_schedule,
                                        params=schedule_params)
    
    parser_devices = subparsers.add_parser('devices')
    parser_devices.set_defaults(func=list_devices)

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
                if hasattr(args, 'func'):
                    await args.func(args, devices)
            except Exception as e:
                print(e)
    except Exception as e:
        print(e)
    finally:
        print(f"Closing all connections")
        await asyncio.gather(*[client.disconnect()
                                for client in devices.values()])

asyncio.run(main())