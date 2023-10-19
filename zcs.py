"""Zuli Command Suite (or for short, zcs) provides a handy way to generate and
interpret Zuli protocol packets.
"""
import datetime
from struct import Struct

CMD_RESET = 2
CMD_VERSION_READ = 6
CMD_FLAGS_READ = 7
CMD_CLOCK_SET = 8
CMD_CLOCK_GET = 9
CMD_NETWORK_SET = 10
CMD_NETWORK_GET = 11
CMD_MODE_SET = 16
CMD_MODE_GET = 17
CMD_ATTRIBUTE_SET = 21
CMD_ATTRIBUTE_GET = 22
CMD_ON = 23
CMD_OFF = 24
CMD_READ = 25
CMD_POWER_READ = 32
CMD_ENERGY_READ_INFO = 33
CMD_ENERGY_READ_ACCUM = 34
CMD_ENERGY_READ_LATCH = 35
CMD_SCHEDULE_INFO_GET = 48
CMD_SCHEDULE_GET = 49
CMD_SCHEDULE_ENABLE = 50
CMD_SCHEDULE_ADD = 51
CMD_SCHEDULE_REMOVE = 52
CMD_SCHEDULE_REMOVE_ALL = 53
CMD_BOOKMARK = 126
CMD_BATCH = 127

def on(brightness = 0) -> bytearray:
    """Creates a packet to turn a smartplug on, optionally at a specified
    brightness
    
    :param brightness: a number between 0 and 100; note that this defaults to
        0, which is functionally equivalent to 100; this is ignored by the
        smartplug if the smartplug is in appliance mode"""
    brightness = min(100, max(0, brightness))
    return bytearray([CMD_ON, 0, 0, 0, 0, brightness, 0, 0, 0])

def off() -> bytearray:
    """Creates a packet to turn a smartplug off"""
    return bytearray([CMD_OFF, 0, 0, 0])

def set_mode(is_appliance = True) -> bytearray:
    """Creates a packet to set the mode of a smartplug
    
    :param is_appliance: by default True, indicating that the smartplug is
        attached to a high power device that does not support dimming (good for
        appliances, non-dimmable lights, etc.); otherwise, the smartplug allows
        dimming
    """
    mode = 0 if is_appliance else 1
    return bytearray([CMD_MODE_SET, mode])

def set_clock(time = datetime.datetime.today()) -> bytearray:
    """Creates a packet to set the clock of a smartplug

    Smartplugs track their own system time for use with schedules, though this
    time does not persist past power cycles.
    """
    weekday = (time.weekday() + 2) % 7
    return bytearray([CMD_CLOCK_SET, time.month, time.day, weekday, time.hour,
                      time.minute, time.second])

def get_clock() -> bytearray:
    """Creates a packet to poll the current system time on a smartplug"""
    return bytearray([CMD_CLOCK_GET])

def parse_get_clock(response: bytearray) -> datetime.datetime:
    """Produces a datetime object from a get clock packet and fails if the
    packet is malformed"""
    year = int.from_bytes(response[2:4])
    return datetime.datetime(year, month=response[4], day=response[5],
                             hour=response[7], minute=response[8],
                             second=response[9])

def read_power() -> bytearray:
    """Creates a packet to read current power consumption"""
    return bytearray([CMD_POWER_READ])

def parse_read_power(response: bytearray) -> int:
    """Returns the current power consumption in watts from a read power packet
    and fails if the packet is malformed"""
    return int.from_bytes(response[2:]) / 1e20

def add_schedule(id: int, time: datetime.time, turn_off=False, weekdays=127,
                 enabled=True) -> bytearray:
    """Creates a packet to push a new schedule to the smartplug
    
    :param id: Unsure if this must be sequential or if using an existing id
        will overwrite
    :param time: The execution time of the schedule
    :param weekdays: A integer between 0 (no days) and 127 (all days) that as a
        bitfield represents the days of the week on which the schedule will
        trigger
    """
    group_id = id
    action = 2 if turn_off else 1
    flags = 1 if enabled else 0
    weekdays = min(127, max(0, weekdays))
    schedule_id = 0
    return bytearray([CMD_SCHEDULE_ADD, group_id, action, 0, 0, time.hour,
                      time.minute, time.second, weekdays, flags, schedule_id])

class Schedule(Struct):
    id: int
    action: int
    time: datetime.time
    weekdays: int
    flags: int
    schedule_id = 0

    def __init__(self, id, time, turn_off=False, weekdays=127, enabled=True):
        self.id = id
        self.turn_off = turn_off
        self.time = time
        self.weekdays = weekdays
        self.enabled = enabled

    def __init__(self, raw: bytearray):
        id = int.from_bytes(raw[0])
        turn_off = raw[1] != 1
        time = datetime.time(hour=raw[4], minute=raw[5], second=raw[6])
        weekdays = raw[7]
        enabled = raw[8] == 1

    def to_bytes() -> bytearray:
        return bytearray([id, action, 0, 0, time.hour,
                      time.minute, time.second, weekdays, flags, schedule_id])
