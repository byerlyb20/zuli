"""Zuli protocol implementation"""
import datetime
from enum import Enum
from typing import TypedDict

ZULI_SERVICE = '04ee929b-bb13-4e77-8160-18552daf06e1'
COMMAND_PIPE = 'ffffff03-bb13-4e77-8160-18552daf06e1'

class ZuliCommand(Enum):
    RESET = 2
    VERSION_READ = 6
    FLAGS_READ = 7
    CLOCK_SET = 8
    CLOCK_GET = 9
    NETWORK_SET = 10
    NETWORK_GET = 11
    MODE_SET = 16
    MODE_GET = 17
    ATTRIBUTE_SET = 21
    ATTRIBUTE_GET = 22
    ON = 23
    OFF = 24
    READ = 25
    POWER_READ = 32
    ENERGY_READ_INFO = 33
    ENERGY_READ_ACCUM = 34
    ENERGY_READ_LATCH = 35
    ENERGY_LATCH_RESET_ALL = 36
    SCHEDULE_INFO_GET = 48
    SCHEDULE_GET = 49
    SCHEDULE_ENABLE = 50
    SCHEDULE_ADD = 51
    SCHEDULE_REMOVE = 52
    SCHEDULE_REMOVE_ALL = 53
    DEFAULT_OUTPUT_SET = 80
    DEFAULT_OUTPUT_GET = 81
    BOOKMARK = 126
    BATCH = 127

class ZuliStatus(Enum):
    SUCCESS = 0
    BUSY = 5
    INVALID_PARAM = 6
    BAD_LENGTH = 15
    ALREADY_SET = 9

    def is_success(self) -> bool:
        return self == ZuliStatus.SUCCESS or self == ZuliStatus.ALREADY_SET

def decode_response_status(response: bytearray) -> ZuliStatus:
    """Returns response status"""
    return ZuliStatus(response[1])

def encode_on(brightness: int = 0) -> bytearray:
    """Message to turn a smartplug on, optionally at a specified brightness
    
    :param brightness: a number between 0 and 100 (otherwise will be trimmed);
        note that this defaults to 0, which is functionally equivalent to 100;
        brightness is ignored by the smartplug when in appliance mode"""
    brightness = min(100, max(0, brightness))
    return bytearray([ZuliCommand.ON.value, 0, 0, 0, 0, brightness, 0, 0, 0])

def encode_off() -> bytearray:
    """Message to turn a smartplug off"""
    return bytearray([ZuliCommand.OFF.value, 0, 0, 0])

def encode_set_mode(is_appliance: bool = True) -> bytearray:
    """Message to set the mode of a smartplug
    
    :param is_appliance: by default True, indicating that the smartplug is
        attached to a high power device that does not support dimming (good for
        appliances, non-dimmable lights, etc.); otherwise, the smartplug allows
        dimming
    """
    mode = 0 if is_appliance else 1
    return bytearray([ZuliCommand.MODE_SET.value, mode])

def encode_set_clock(time: datetime.datetime) -> bytearray:
    """Message to set the clock of a smartplug

    Smartplugs maintain system time for schedules, though the time does not
    persist past power cycles.
    """
    year = time.year.to_bytes(2)
    weekday = ((time.weekday() + 1) % 7) + 1
    return bytearray([ZuliCommand.CLOCK_SET.value, year[0], year[1], time.month, time.day,
                      weekday, time.hour, time.minute, time.second])

def encode_get_clock() -> bytearray:
    """Message to to poll the current system time on a smartplug"""
    return bytearray([ZuliCommand.CLOCK_GET.value])

def decode_get_clock(response: bytearray) -> datetime.datetime:
    """Produces a datetime object from a get clock packet and fails if the
    packet is malformed"""
    year = int.from_bytes(response[2:4])
    return datetime.datetime(year, month=response[4], day=response[5],
                             hour=response[7], minute=response[8],
                             second=response[9])

def encode_read_power() -> bytearray:
    """Message to to read current power consumption"""
    return bytearray([ZuliCommand.POWER_READ.value])

class Power(TypedDict):
    irms_ma: int
    power_mw: int
    power_factor: int
    voltage_mv: int

def decode_read_power(response: bytearray) -> Power:
    """Returns the current power consumption in watts from a read power packet
    and fails if the packet is malformed"""
    irms_ma = int.from_bytes(response[2:4])
    power_mw = int.from_bytes(response[4:7])
    power_factor = int.from_bytes(response[7:9])
    voltage_mv = int.from_bytes(response[9:12])
    return Power(irms_ma=irms_ma, power_mw=power_mw, power_factor=power_factor,
                 voltage_mv=voltage_mv)

class ScheduleAction(Enum):
    ON = 1
    OFF = 2

class Schedule():
    """A representation of a schedule that can be used to turn a smartplug on
    or off at a specific time"""
    WEEKDAY_SYMBOL = "MTWTFSS"

    def __init__(self, time: datetime.time, id: int = 0,
                 action: ScheduleAction = ScheduleAction.ON,
                 weekdays: list[bool] = [True] * 7, enabled: bool = True,
                 schedule_id: int = 0):
        self.id = id
        self.action = action
        self.time = time
        self.weekdays = weekdays
        self.enabled = enabled
        self.schedule_id = schedule_id

    @staticmethod
    def from_bytes(raw: bytearray):
        id = raw[0]
        action = ScheduleAction(raw[1])
        time = datetime.time(hour=raw[4], minute=raw[5], second=raw[6])
        # Represented from index 0 == Monday ... 6 == Sunday as does datetime,
        # note that this is a departure from the way the smartplugs consider
        # Sunday to be the first day of the week
        weekdays = []
        for i in range(7):
            # Account the start of the week difference between the protocol
            # and Python datetime
            i = (i + 1) % 7
            bitflag = 1 << i
            weekdays.append(raw[7] & bitflag == bitflag)
        enabled = raw[8] == 1
        schedule_id = raw[9]
        return Schedule(time, id=id, action=action, weekdays=weekdays,
                        enabled=enabled, schedule_id=schedule_id)

    def to_bytes(self) -> bytearray:
        weekdays = 0
        for i in range(7):
            # Account the start of the week difference between the protocol
            # and Python datetime
            shift = (i + 1) % 7
            bitflag = self.weekdays[i] << shift
            weekdays |= bitflag
        return bytearray([self.id, self.action.value, 0, 0, self.time.hour,
                      self.time.minute, self.time.second, weekdays,
                      self.enabled, self.schedule_id])
    
    def without_id(self) -> bytearray:
        """Returns a trimmed byte representation of the schedule without
        identifiers, useful when removing schedules"""
        raw = self.to_bytes()
        return raw[1:8]
    
    def __str__(self):
        weekdays_sym = map(lambda i : self.WEEKDAY_SYMBOL[i]
                           if self.weekdays[i] else "-", range(7))
        weekdays_str = " ".join(weekdays_sym)
        action_str = "Turn On" if self.action == ScheduleAction.ON else "Turn Off"
        enabled_str = "Enabled" if self.enabled else "Disabled"
        return f"{action_str}  {weekdays_str}  at {self.time.isoformat()} ({enabled_str})"

def encode_add_schedule(schedule: Schedule) -> bytearray:
    """Message to to push a new schedule to the smartplug
    """
    packet = bytearray([ZuliCommand.SCHEDULE_ADD.value])
    packet.extend(schedule.to_bytes())
    return packet

def encode_get_schedule(i: int) -> bytearray:
    """Message to to get a single schedule saved to the smartplug

    This packet will typically be sent n times, n being the number of schedules
    saved to the smartplug, after first sending a get schedule info packet to
    determine the value of n.
    
    :param i: a number between 1 and the number of schedules on the smartplug;
        the number that corresponds to a specific schedule does not stay the
        same between operations that change schedules
    """
    return bytearray([ZuliCommand.SCHEDULE_GET.value, i])

def decode_get_schedule(response: bytearray) -> Schedule:
    """Returns a single schedule from a get schedule packet and fails if the
    packet is malformed"""
    return Schedule.from_bytes(response[2:])

def encode_get_schedule_info() -> bytearray:
    """Message to to get schedule info"""
    return bytearray([ZuliCommand.SCHEDULE_INFO_GET.value, 0])

class ScheduleInfo(TypedDict):
    num_schedules: int
    max_schedules: int

def decode_get_schedule_info(response: bytearray) -> ScheduleInfo:
    """Returns a tuple of the number of events and the maximum supported number
    and fails if the packet is malformed"""
    return ScheduleInfo(num_schedules=response[2], max_schedules=response[3])

def encode_remove_schedule(schedule: Schedule) -> bytearray:
    """Message to to remove a single schedule saved to the smartplug"""
    packet = bytearray([ZuliCommand.SCHEDULE_REMOVE.value, 0])
    packet.extend(schedule.without_id())
    return packet

def encode_remove_all_schedules() -> bytearray:
    """Untested. Reconstructed from Zuli Android app"""
    packet = bytearray([ZuliCommand.SCHEDULE_REMOVE_ALL.value])
    confirm_remove_all = 46140
    packet.extend(confirm_remove_all.to_bytes(2))
    return packet

def encode_read_energy_info() -> bytearray:
    """Untested. Reconstructed from Zuli Android app"""
    return bytearray([ZuliCommand.ENERGY_READ_INFO.value, 0])

class EnergyInfo(TypedDict):
    a: int
    b: int
    c: int
    d: int

def decode_read_energy_info(response: bytearray) -> EnergyInfo:
    a = response[2]
    b = response[4]
    c = int.from_bytes(response[5:7])
    d = int.from_bytes(response[7:9])
    return EnergyInfo(a=a, b=b, c=c, d=d)

def encode_latch_data(latch_id: int) -> bytearray:
    """Untested. Reconstructed from Zuli Android app"""
    packet = bytearray([ZuliCommand.ENERGY_READ_LATCH.value, 0])
    packet.extend(latch_id.to_bytes(2))
    return packet

class LatchData(TypedDict):
    value: int
    duration: int
    unix_time_sec: int
    unix_time_ms: int

def decode_read_latch_data(response: bytearray) -> LatchData:
    """Untested. Reconstructed from Zuli Android app"""
    value = int.from_bytes(response[2:9])
    duration = int.from_bytes(response[9:14])
    unix_time_sec = int.from_bytes(response[14:18])
    unix_time_ms = int.from_bytes(response[18:20])
    return LatchData(value=value, duration=duration,
                     unix_time_sec=unix_time_sec, unix_time_ms=unix_time_ms)

def encode_reset_all_latches(num_latches: int) -> bytearray:
    """Untested. Reconstructed from Zuli Android app"""
    packet = bytearray([ZuliCommand.ENERGY_LATCH_RESET_ALL.value, 0])
    packet.extend(num_latches.to_bytes(2))
    confirm_reset_all = 5693
    packet.extend(confirm_reset_all.to_bytes(2))
    return packet

def encode_reset_plug() -> bytearray:
    """Untested. Reconstructed from Zuli Android app"""
    packet = bytearray([ZuliCommand.RESET.value, ZuliCommand.RESET.value, 0])
    confirm_reset = 22890
    packet.extend(confirm_reset.to_bytes(2))
    return packet
