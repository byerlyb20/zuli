from . import protocol
from . import smartplug
import asyncio
import sys
import argparse
from datetime import time
from bleak import BleakScanner
from bleak import BleakClient

class InteractiveArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None): # pyright: ignore[reportIncompatibleMethodOverride]
        if message:
            raise argparse.ArgumentError(argument=None, message=message)

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
            device = result[0] if isinstance(result, tuple) else None
            result = result[1] if isinstance(result, tuple) else result

            if isinstance(result, bool):
                result = "Success" if result else "Failure"
            elif isinstance(result, list):
                results = result
                result = ""
                for item in results:
                    result += f"{item}\n"
                result = result.strip()
            
            if device != None:
                if isinstance(result, str) and '\n' in result:
                    print(f"\n==== {device.address} ====\n")
                    print(result)
                else:
                    print(f"{device.address} : {result}")
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
    parser = InteractiveArgumentParser(prog="zuli", exit_on_error=False)
    subparsers = parser.add_subparsers()

    parent_parser = InteractiveArgumentParser(add_help=False)
    parent_parser.add_argument('-d', '--devices', action='extend', nargs='+',
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
    parser_schedule.set_defaults(func=wrap_method(smartplug.get_clients_schedules))

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
        return [protocol.Schedule(time=a.time, action=protocol.ScheduleAction.OFF
                                            if a.action == "off"
                                            else protocol.ScheduleAction.ON)]
    parser_schedule_add.set_defaults(func=wrap_method(smartplug.add_schedule),
                                        params=schedule_params)
    
    parser_devices = subparsers.add_parser('devices')
    parser_devices.set_defaults(func=list_devices)

    subparsers.add_parser('quit')

    return parser

async def main():
    devices: dict[str, BleakClient] = {}

    async def discover():
        try:
            async with BleakScanner(service_uuids=[protocol.ZULI_SERVICE]) as scanner:
                async with asyncio.TaskGroup() as tg:
                    async for (device, advertisement_data) in scanner.advertisement_data():
                        if device.address not in devices or not devices[device.address].is_connected:
                            client = BleakClient(device)
                            devices[device.address] = client

                            async def try_connect(client: BleakClient):
                                try:
                                    await client.connect()
                                except Exception:
                                    pass
                            tg.create_task(try_connect(client))
        except asyncio.CancelledError:
            return
    discovery_task = asyncio.create_task(discover())

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
        print(f"Stopping discovery and closing all connections")
        discovery_task.cancel()
        await discovery_task
        await asyncio.gather(*[client.disconnect()
                                for client in devices.values()])

asyncio.run(main())
