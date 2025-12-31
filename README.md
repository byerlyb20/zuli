This project serves to reconstruct and document the protocol used to interact
with Zuli smartplugs. Included is a Python CLI that can be used to perform
basic operations on Zuli devices (turn them on/off, set schedules, check power
usage, etc.). This project is by no means mature or complete or even under
active development. I originally started the project out of curiosity, although
I do find myself using it from time to time. (I use it to manage several Zuli smartplugs
running various schedules for lights at home.) Whatever you use it for, I hope
you will find it to be useful in your hacking ;)

## How to use

Make sure you are in the `src` directory and run `python zuli.py` to open a simple command prompt. This utility does not run as a standalone command as you might expect. This design allows BLE connections with devices to be kept open in between commands.

> [!NOTE]
> macOS users must give Terminal (or your app of choice) Bluetooth access for this utility to work.

First, you might query the current list of discovered smartplugs. My output shows UUIDs instead of true MAC addresses due to the way the Bluetooth stack on macOS works; your output may look a little different.

```
>>> devices
1A494372-A92F-4710-BFBF-07DBD8604702
693907F9-3013-43AF-B8DC-8839686CBE59
74215D76-212E-45D5-BA05-AF289EB34416
```

Now, you could turn all of the discovered devices on with:

```
>>> on
```

Or, you could turn on a specific device.

```
>>> on -d 1A49
```

To see a complete list of commands, type garbage into the prompt:

```
argument {on,off,mode,power,time,synctime,schedules,remove_schedule,add_schedule,devices,quit}: invalid choice: 'qwertyasdf' (choose from on, off, mode, power, time, synctime, schedules, remove_schedule, add_schedule, devices, quit)
```

## Next steps

I would love to get a Home Assistant integration working.

## About Zuli smartplugs

Zuli smartplugs were announced
on Kickstarter in 2015 with an iOS app announced at launch and an Android app promised shortly
thereafter. The company has recently discontinued support for both apps, though it is still possible
to use their smartplugs since they operate locally via Bluetooth.