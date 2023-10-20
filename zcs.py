"""Zuli Command Suite (or for short, zcs) provides a handy way to generate and
interpret Zuli protocol packets.
"""
from typing import List
import datetime

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

class Schedule():
    """A representation of a schedule that can be used to turn a smartplug on
    or off at a specific time"""
    ACTION_ON = 1
    ACTION_OFF = 2

    def __init__(self, id: int, time: datetime.time, action=ACTION_ON,
                 weekdays=[True] * 7, enabled=True, schedule_id=0):
        self.id = id
        self.action = action
        self.time = time
        self.weekdays = weekdays
        self.enabled = enabled
        self.schedule_id = schedule_id

    def from_bytes(raw: bytearray):
        id = raw[0]
        action = raw[1]
        time = datetime.time(hour=raw[4], minute=raw[5], second=raw[6])
        # Represented from index 0 == Monday ... 6 == Sunday as does datetime,
        # note that this is a departure from the way the smartplugs consider
        # Sunday to be the first day of the week
        weekdays = []
        for i in range(7):
            # Account for weeks beginning on different days
            i = (i + 1) % 7
            bitflag = 1 << i
            weekdays.append(raw[7] & bitflag == bitflag)
        enabled = raw[8] == 1
        schedule_id = raw[9]
        return Schedule(id, time, action=action, weekdays=weekdays,
                        enabled=enabled, schedule_id=schedule_id)

    def to_bytes(self) -> bytearray:
        weekdays = 0
        for i in range(7):
            # Account for weeks beginning on different days
            shift = (i + 1) % 7
            bitflag = self.weekdays[i] << shift
            weekdays |= bitflag
        return bytearray([self.id, self.action, 0, 0, self.time.hour,
                      self.time.minute, self.time.second, weekdays,
                      self.enabled, self.schedule_id])
    
    def as_anonymous(self) -> bytearray:
        """Returns a trimmed byte representation of the schedule without
        identifiers, useful when removing schedules"""
        raw = self.to_bytes()
        return raw[1:9]

def add_schedule(schedule: Schedule) -> bytearray:
    """Creates a packet to push a new schedule to the smartplug
    """
    packet = bytearray([CMD_SCHEDULE_ADD])
    packet.extend(schedule.to_bytes())
    return packet

def get_schedule() -> bytearray:
    """Creates a packet to get a single schedule saved to the smartplug"""
    return bytearray([CMD_SCHEDULE_GET])

def parse_get_schedule(response: bytearray) -> Schedule:
    """Returns a single schedule from a get schedule packet and fails if the
    packet is malformed"""
    return Schedule.from_bytes(response[2:])