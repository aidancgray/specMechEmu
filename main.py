#!/usr/bin/env python3
# specMechEmu.py
# 12/17/2020
# Aidan Gray
# aidan.gray@idg.jhu.edu
#
# This is an emulator for the BOSS specMech hardware microcontroller. The
# intent is to use this emulator to simulate the specMech mcu during
# development of the specActor. Functionality is based on the document:
#   "specMech Communications Guide" provided by Alan Uomoto.

from contextlib import suppress
import asyncio
import functools as ft
import time
# import sys

# Dictionary of valid verbs with their valid objects
verbDict = {
    'e': ['e', 'l', 'r', 's'],
    'o': ['s', 'l', 'r'],
    'c': ['s', 'l', 'r'],
    'M': ['a', 'b', 'c', 'p'],
    'm': ['a', 'b', 'c', 'p', 'H'],
    's': ['t'],
    'r': ['a', 'b', 'c', 'B', 'e', 'i', 'o', 'p', 's', 't', 'v'],
    'R': []
}


# specMech Microcontroller
class SpecMech:
    def __init__(self, name, bootTime, clockDelta, version):
        self.name = name
        self.bootTime = bootTime
        self.clockDelta = clockDelta
        self.version = version
        self.rebooted = True

    def get_time(self):
        tCur = time.mktime(time.gmtime(time.time()))
        clockTime = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime(tCur + self.clockDelta))
        return clockTime

    def set_clock_delta(self, setTime):
        tSet = time.mktime(time.strptime(setTime, '%Y-%m-%dT%H:%M:%SZ'))
        tCur = time.mktime(time.gmtime(time.time()))
        self.clockDelta = tSet - tCur

    def reboot(self):
        self.rebooted = True
        self.clockDelta = 0

    def reboot_ack(self):
        self.rebooted = False


# For the Shutter and Hartmann Doors
class Door:
    def __init__(self, name, state):
        self.name = name
        self.state = state

    async def open(self):
        if self.state == 'c':
            self.state = 't'
            await asyncio.sleep(0.5)
            self.state = 'o'

    async def close(self):
        if self.state == 'o':
            self.state = 't'
            await asyncio.sleep(0.5)
            self.state = 'c'


# Collimator Pistons
class Piston:
    def __init__(self, name, position):
        self.name = name
        self.position = position

    async def move_absolute(self, loc):
        self.position = loc

    async def move_relative(self, dist):
        self.position = self.position + dist

    def home(self):
        self.position = 0


# Accelerometer
class Accelerometer:
    def __init__(self, name, xPos, yPos, zPos):
        self.name = name
        self.xPos = xPos
        self.yPos = yPos
        self.zPos = zPos


# Ion Pump
class IonPump:
    def __init__(self, name, voltage):
        self.name = name
        self.voltage = voltage


# Environment (Temperature & Humidity)
class Environment:
    def __init__(self, name, temp, hum):
        self.name = name
        self.temperature = temp
        self.humidity = hum


# Air Pressure
class Pressure:
    def __init__(self, name, pressure):
        self.name = name
        self.pressure = pressure


# Cancels all running asyncio Tasks
async def shutdown():
    print('~~~ Shutting down...')
    print('~~~ cancelling task:')
    i = 1
    for task in asyncio.all_tasks():
        print(f'~~~ {i}')
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        i += 1
    print('~~~ Done.')


# gets the checksum of the NMEA response and adds it to the reply
def add_checksum(msg):
    tmpCheckSum = ft.reduce(lambda x, y: x ^ y, msg.encode())
    checkSum = '{:X}'.format(tmpCheckSum)
    return '$' + msg + '*' + checkSum + '\r\n'


# processes the command
async def process_command(writer, msg):
    verb = msg[0]
    rem = ''
    reply = ''

    if specMech.rebooted:
        if msg == '!\r' or msg == '!\r\n':
            specMech.rebooted = False

        reply = reply + '\r\n>'
        print(f"Reply: {reply!r}")
        writer.write(reply.encode())

    else:
        if verb == 'R':
            specMech.reboot()
            reply = reply + '\r\n>'
            print(f"Reply: {reply!r}")
            writer.write(reply.encode())
        else:
            obj = msg[1]

            if msg[-1:] == '\n':
                rem = msg[2:-2]  # Get the remainder of the message minus \r\n
            elif msg[-1:] == '\r':
                rem = msg[2:-1]  # Get the remainder of the message minus \r

            if verb == 'M':  # Check if verb is abs move
                reply = reply + '\r\n>'
                print(f"Reply: {reply!r}")
                writer.write(reply.encode())

                move = int(rem)
                if obj == 'p':
                    taskA = asyncio.create_task(aColl.move_absolute(move))
                    taskB = asyncio.create_task(bColl.move_absolute(move))
                    taskC = asyncio.create_task(cColl.move_absolute(move))
                    await asyncio.gather(taskA, taskB, taskC)

                elif obj == 'a':
                    await aColl.move_absolute(move)

                elif obj == 'b':
                    await bColl.move_absolute(move)

                elif obj == 'c':
                    await cColl.move_absolute(move)

            elif verb == 'm':  # Check if verb is rel move
                reply = reply + '\r\n>'
                print(f"Reply: {reply!r}")
                writer.write(reply.encode())

                move = int(rem)
                if obj == 'p':
                    taskA = asyncio.create_task(aColl.move_relative(move))
                    taskB = asyncio.create_task(bColl.move_relative(move))
                    taskC = asyncio.create_task(cColl.move_relative(move))
                    await asyncio.gather(taskA, taskB, taskC)

                elif obj == 'a':
                    await aColl.move_relative(move)

                elif obj == 'b':
                    await bColl.move_relative(move)

                elif obj == 'c':
                    await cColl.move_relative(move)

            elif verb == 's':  # Check if verb is set time
                reply = reply + '\r\n>'
                print(f"Reply: {reply!r}")
                writer.write(reply.encode())
                try:
                    specMech.set_clock_delta(rem)
                except ValueError:
                    pass

            elif rem == '':
                if verb == 'o':  # Check if verb is open/close
                    reply = reply + '\r\n>'
                    print(f"Reply: {reply!r}")
                    writer.write(reply.encode())

                    if obj == 's':
                        await shutter.open()

                    elif obj == 'l':
                        await leftHart.open()

                    elif obj == 'r':
                        await rightHart.open()

                elif verb == 'c':
                    reply = reply + '\r\n>'
                    print(f"Reply: {reply!r}")
                    writer.write(reply.encode())

                    if obj == 's':
                        await shutter.close()

                    elif obj == 'l':
                        await leftHart.close()

                    elif obj == 'r':
                        await rightHart.close()

                elif verb == 'e':  # Check if verb is expose
                    reply = reply + '\r\n>'
                    print(f"Reply: {reply!r}")
                    writer.write(reply.encode())

                    # Depending on object, go through expose routine
                    if obj == 's':
                        taskL = asyncio.create_task(leftHart.open())
                        taskR = asyncio.create_task(rightHart.open())
                        await asyncio.gather(taskL, taskR)
                        await shutter.open()

                    elif obj == 'l':
                        taskL = asyncio.create_task(leftHart.open())
                        taskR = asyncio.create_task(rightHart.close())
                        await asyncio.gather(taskL, taskR)
                        await shutter.open()

                    elif obj == 'r':
                        taskL = asyncio.create_task(leftHart.close())
                        taskR = asyncio.create_task(rightHart.open())
                        await asyncio.gather(taskL, taskR)
                        await shutter.open()

                    elif obj == 'e':
                        taskL = asyncio.create_task(leftHart.close())
                        taskR = asyncio.create_task(rightHart.close())
                        await asyncio.gather(taskL, taskR)
                        await shutter.close()

                elif verb == 'r':  # Check if verb is report
                    if obj == 'B':
                        btm = specMech.bootTime
                        reply = add_checksum(f"S2BTM,{btm}")

                    elif obj == 'a':
                        mra = aColl.position
                        reply = add_checksum(f"S2MRA,{mra}")

                    elif obj == 'b':
                        mrb = bColl.position
                        reply = add_checksum(f"S2MRB,{mrb}")

                    elif obj == 'c':
                        mrc = cColl.position
                        reply = add_checksum(f"S2MRC,{mrc}")

                    elif obj == 'e':
                        envT0 = env0.temperature
                        envT1 = env1.temperature
                        envT2 = env2.temperature
                        envT3 = env3.temperature
                        envH0 = env0.humidity
                        envH1 = env1.humidity
                        envH2 = env2.humidity
                        envH3 = env3.humidity
                        reply = f"S2ENV,{envT0}C,{envH0}%,0,{envT1}C,{envH1}%,1," \
                                f"{envT2}C,{envH2}%,2,{envT3}C,{envH3}%,3"
                        reply = add_checksum(reply)

                    elif obj == 'i':
                        rION = rIon.voltage
                        bION = bIon.voltage
                        reply = add_checksum(f"S2ION,{rION},r,{bION},b")

                    elif obj == 'o':
                        xACC = accel.xPos
                        yACC = accel.yPos
                        zACC = accel.zPos
                        reply = add_checksum(f"S2ACC,{xACC},{yACC},{zACC}")

                    elif obj == 'p':
                        sPNU = shutter.state
                        lPNU = leftHart.state
                        rPNU = rightHart.state
                        pPNU = airPress.pressure
                        reply = add_checksum(f"S2PNU,{sPNU},s,{lPNU},l,{rPNU},r,{pPNU},p")

                    elif obj == 't':
                        tTIM = specMech.get_time()
                        reply = add_checksum(f"S2TIM,{tTIM}")

                    elif obj == 'v':
                        vVER = specMech.version
                        reply = add_checksum(f"S2VER,{vVER}")

                    elif obj == 's':
                        # Get all of the statuses
                        btm = specMech.bootTime
                        reply = add_checksum(f"S2BTM,{btm}")
                        mra = aColl.position
                        reply = reply + add_checksum(f"S2MRA,{mra}")
                        mrb = bColl.position
                        reply = reply + add_checksum(f"S2MRB,{mrb}")
                        mrc = cColl.position
                        reply = reply + add_checksum(f"S2MRC,{mrc}")
                        envT0 = env0.temperature
                        envT1 = env1.temperature
                        envT2 = env2.temperature
                        envT3 = env3.temperature
                        envH0 = env0.humidity
                        envH1 = env1.humidity
                        envH2 = env2.humidity
                        envH3 = env3.humidity
                        reply = reply + add_checksum(f"S2ENV,{envT0}C,{envH0}%,0,{envT1}C,{envH1}%,1,"
                                                     f"{envT2}C,{envH2}%,2,{envT3}C,{envH3}%,3")
                        rION = rIon.voltage
                        bION = bIon.voltage
                        reply = reply + add_checksum(f"S2ION,{rION},r,{bION},b")
                        xACC = accel.xPos
                        yACC = accel.yPos
                        zACC = accel.zPos
                        reply = reply + add_checksum(f"S2ACC,{xACC},{yACC},{zACC}")
                        sPNU = shutter.state
                        lPNU = leftHart.state
                        rPNU = rightHart.state
                        pPNU = airPress.pressure
                        reply = reply + add_checksum(f"S2PNU,{sPNU},s,{lPNU},l,{rPNU},r,{pPNU},p")
                        tTIM = specMech.get_time()
                        reply = reply + add_checksum(f"S2TIM,{tTIM}")
                        vVER = specMech.version
                        reply = reply + add_checksum(f"S2VER,{vVER}")

                    reply = reply + '\r\n>'
                    print(f"Reply: {reply!r}")
                    writer.write(reply.encode())


# parses the message to check if command is valid
async def check_data(msg):
    verb = msg[0]
    errorResp = "$S2ERR*24\r\n"

    if specMech.rebooted:
        if msg != '!\r' and msg != '!\r\n':
            return "\r\n!"
        else:
            return ''

    if verb in verbDict:  # Check if the verb is valid
        if verb == 'R':
            return ''

        obj = msg[1]
        objList = verbDict[verb]

        if obj in objList:  # Check if the object is valid for the given verb
            if msg[-1:] == '\n':
                rem = msg[2:-2]  # Get the remainder of the message minus \r\n
            elif msg[-1:] == '\r':
                rem = msg[2:-1]  # Get the remainder of the message minus \r
            else:
                return errorResp

            if verb == 'M':  # Check if verb is abs move
                try:
                    int(rem)

                except ValueError:
                    return errorResp

            elif verb == 'm':  # Check if verb is rel move
                try:
                    int(rem)

                except ValueError:
                    return errorResp

            elif verb == 's':  # Check if verb is set time
                try:
                    time.mktime(time.strptime(rem, '%Y-%m-%dT%H:%M:%SZ'))

                except ValueError:
                    return errorResp

        else:
            return errorResp
    else:
        return errorResp

    return ''


async def handle_data(reader, writer):
    dataLoop = True
    while dataLoop:
        try:
            data = await reader.read(100)
            message = data.decode()
            addr = writer.get_extra_info('peername')
            print(f"Received {message!r} from {addr!r}")

            if message[:-2] == 'q':
                dataLoop = False

            elif len(message) == 0:
                check = '$S2ERR*24\r\n\r\n>'
                print(f'Check: {check!r}')
                writer.write(check.encode())
                await writer.drain()

            else:
                check = await check_data(message)
                print(f"Check: {check!r}")
                writer.write(check.encode())

                asyncio.create_task(process_command(writer, message))

                await writer.drain()

        except Exception as e:
            print("Unexpected error:", e)
            await shutdown()

    await writer.drain()
    writer.close()
    await shutdown()


async def main():
    server = await asyncio.start_server(handle_data, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")

    async with server:
        with suppress(asyncio.CancelledError):
            await server.serve_forever()


if __name__ == "__main__":
    specMech = SpecMech('specMech',
                        time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
                        0,
                        '2020-12-16')

    shutter = Door('s', 'c')
    leftHart = Door('l', 'c')
    rightHart = Door('r', 'c')

    aColl = Piston('a', 234324)
    bColl = Piston('b', 234324)
    cColl = Piston('c', 234324)

    accel = Accelerometer('accel', 32, 100, 989)

    rIon = IonPump('r', 1432)
    bIon = IonPump('b', 1243)

    env0 = Environment('0', 12, 44)
    env1 = Environment('1', 13, 42)
    env2 = Environment('2', 11, 48)
    env3 = Environment('3', 12, 43)

    airPress = Pressure('p', 1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('~~~Keyboard Interrupt~~~')
