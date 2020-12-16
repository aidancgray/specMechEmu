#!/usr/bin/env python3
import asyncio
import functools as ft
import time

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


# General Object Class
class Object:
    def __init__(self, name):
        self.name = name


# specMech Microcontroller
class SpecMech(Object):
    def __init__(self, name, bootTime, clockTime, version):
        super().__init__(name)
        self.bootTime = bootTime
        self.clockTime = clockTime
        self.version = version
        self.rebooted = True

    def reboot(self):
        self.rebooted = True

    def reboot_ack(self):
        self.rebooted = False


# For the Shutter and Hartmann Doors
class Door(Object):
    def __init__(self, name, state):
        super().__init__(name)
        self.state = state

    def open(self):
        self.state = 't'
        # wait for 5 seconds non-blocking
        self.state = 'o'

    def close(self):
        self.state = 't'
        # wait for 5 seconds non-blocking
        self.state = 'c'


# Collimator Pistons
class Piston(Object):
    def __init__(self, name, position):
        super().__init__(name)
        self.position = position

    async def move_absolute(self, loc):
        self.position = loc

    async def move_relative(self, dist):
        self.position = self.position + dist

    def home(self):
        self.position = 0


# Accelerometer
class Accelerometer(Object):
    def __init__(self, name, xPos, yPos, zPos):
        super().__init__(name)
        self.xPos = xPos
        self.yPos = yPos
        self.zPos = zPos


# Ion Pump
class IonPump(Object):
    def __init__(self, name, voltage):
        super().__init__(name)
        self.voltage = voltage


# Environment (Temperature & Humidity)
class Environment(Object):
    def __init__(self, name, temp, hum):
        super().__init__(name)
        self.temperature = temp
        self.humidity = hum


# Air Pressure
class Pressure(Object):
    def __init__(self, name, pressure):
        super().__init__(name)
        self.pressure = pressure


# gets the checksum of the NMEA response and adds it to the reply
def add_checksum(msg):
    tmpCheckSum = ft.reduce(lambda x, y: x ^ y, msg.encode())
    checkSum = '{:X}'.format(tmpCheckSum)
    return '$' + msg + '*' + checkSum + '\r\n'


# processes the command
async def process_command(msg):
    verb = msg[0]
    rem = ''
    tmpReply = ''

    if specMech.rebooted:
        if msg == '!\r' or msg == '!\r\n':
            specMech.rebooted = False
            return ''
        else:
            return ''

    if verb == 'R':
        specMech.reboot()
        return ''

    obj = msg[1]

    if msg[-1:] == '\n':
        rem = msg[2:-2]  # Get the remainder of the message minus \r\n
    elif msg[-1:] == '\r':
        rem = msg[2:-1]  # Get the remainder of the message minus \r

    if verb == 'M':  # Check if verb is abs move
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
        specMech.clockTime = rem

    elif rem == '':
        if verb == 'o':  # Check if verb is open/close
            if obj == 's':
                shutter.open()

            elif obj == 'l':
                leftHart.open()

            elif obj == 'r':
                rightHart.open()

        elif verb == 'c':
            if obj == 's':
                shutter.close()

            elif obj == 'l':
                leftHart.close()

            elif obj == 'r':
                rightHart.close()

        elif verb == 'e':  # Check if verb is expose
            # Depending on object, go through expose routine
            if obj == 's':
                leftHart.open()
                rightHart.open()
                shutter.open()

            elif obj == 'l':
                leftHart.open()
                shutter.open()

            elif obj == 'r':
                rightHart.open()
                shutter.open()

            elif obj == 'e':
                leftHart.close()
                rightHart.close()
                shutter.close()

        elif verb == 'r':  # Check if verb is report
            if obj == 'B':
                btm = specMech.bootTime
                tmpReply = f"S2BTM,{btm}"

            elif obj == 'a':
                mra = aColl.position
                tmpReply = f"S2MRA,{mra}"

            elif obj == 'b':
                mrb = bColl.position
                tmpReply = f"S2MRB,{mrb}"

            elif obj == 'c':
                mrc = cColl.position
                tmpReply = f"S2MRC,{mrc}"

            elif obj == 'e':
                envT0 = env0.temperature
                envT1 = env1.temperature
                envT2 = env2.temperature
                envT3 = env3.temperature
                envH0 = env0.humidity
                envH1 = env1.humidity
                envH2 = env2.humidity
                envH3 = env3.humidity
                tmpReply = f"S2ENV,{envT0}C,{envH0}%,0,{envT1}C,{envH1}%,1," \
                           f"{envT2}C,{envH2}%,2,{envT3}C,{envH3}%,3"

            elif obj == 'i':
                rION = rIon.voltage
                bION = bIon.voltage
                tmpReply = f"S2ION,{rION},r,{bION},b"

            elif obj == 'o':
                xACC = accel.xPos
                yACC = accel.yPos
                zACC = accel.zPos
                tmpReply = f"S2ACC,{xACC},{yACC},{zACC}"

            elif obj == 'p':
                sPNU = shutter.state
                lPNU = leftHart.state
                rPNU = rightHart.state
                pPNU = airPress.pressure
                tmpReply = f"S2PNU,{sPNU},s,{lPNU},l,{rPNU},r,{pPNU},p"

            elif obj == 't':
                tTIM = specMech.clockTime
                tmpReply = f"S2TIM,{tTIM}"

            elif obj == 'v':
                vVER = specMech.version
                tmpReply = f"S2VER,{vVER}"

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
                tTIM = specMech.clockTime
                reply = reply + add_checksum(f"S2TIM,{tTIM}")
                vVER = specMech.version
                reply = reply + add_checksum(f"S2VER,{vVER}")
                return reply

            else:
                return ''

            return add_checksum(tmpReply)

    return ''


# parses the message to check if command is valid
async def check_data(msg):
    verb = msg[0]

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
                return "$S2ERR*24\r\n"

            if verb == 'M':  # Check if verb is abs move
                try:
                    int(rem)

                except ValueError:
                    return "$S2ERR*24\r\n"

            elif verb == 'm':  # Check if verb is rel move
                try:
                    int(rem)

                except ValueError:
                    return "$S2ERR*24\r\n"

            elif verb == 's':  # Check if verb is set time
                try:
                    str(rem)

                except ValueError:
                    return "$S2ERR*24\r\n"

        else:
            return "$S2ERR*24\r\n"
    else:
        return "$S2ERR*24\r\n"

    return ''


async def handle_data(reader, writer):
    loop = True
    while loop:
        data = await reader.read(100)
        message = data.decode()
        addr = writer.get_extra_info('peername')
        print(f"Received {message!r} from {addr!r}")

        if message[:-2] == 'q':
            loop = False
        else:
            check = await check_data(message)
            print(f"Check: {check!r}")
            writer.write(check.encode())

            reply = await process_command(message)
            reply = reply + '\r\n>'
            print(f"Reply: {reply!r}")
            writer.write(reply.encode())
            await writer.drain()

    await writer.drain()
    writer.close()


async def main():
    server = await asyncio.start_server(handle_data, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    specMech = SpecMech('specMech',
                        time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
                        time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
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

    asyncio.run(main())
