#!/usr/bin/env python3
import asyncio
import functools as ft
import time

# Dictionary of valid verbs with their valid objects
verbDict = {
    'e': ['e', 'l', 'r', 's'],
    'o': ['s', 'l', 'r', 'b'],
    'c': ['s', 'l', 'r', 'b'],
    'M': ['a', 'b', 'c', 'p'],
    'm': ['a', 'b', 'c', 'p', 'H'],
    's': ['t'],
    'r': ['A', 'B', 'e', 'i', 'o', 'p', 's', 't', 'v'],
    'R': []
}

# Dictionary of hardware and their associated states/values
hardwareDict = {
    'a': 0,                 # Collimator Motor Positions
    'b': 0,
    'c': 0,

    'B': '0-0-0T0:0:0Z',    # Boot time

    'e': {                  # Environment
        'T0': 12,           # Temperature
        'H0': 44,           # Humidity
        'T1': 13,
        'H1': 42,
        'T2': 11,
        'H2': 48,
        'T3': 12,
        'H3': 43},

    'i': {                  # Ion Pump Voltage
        'r': 1432,
        'b': 1243},

    'o': {                  # Accelerometer in milli-g
        'x': 32,
        'y': 100,
        'z': 989},

    'p': {
        's': 'c',           # Shutter
        'l': 'c',           # Left Hartmann
        'r': 'c',           # Right Hartmann
        'p': 1},          # Air Pressure

    't': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime()),
    'v': '2020-11-30'
}


# gets the checksum of the NMEA response and adds it to the reply
def add_checksum(msg):
    tmpCheckSum = ft.reduce(lambda x, y: x ^ y, msg.encode())
    checkSum = '{:X}'.format(tmpCheckSum)
    return '$'+msg+'*'+checkSum


# opens/closes the object by setting state to t, waiting,
# then setting to open/close
async def open_close(v, o):
    hardwareDict[o] = 't'
    await asyncio.sleep(5)
    hardwareDict[o] = v


# absolute move the collimator motors by setting state to t, waiting,
# then setting to final position
async def move_abs(motor, move):
    currentPosition = hardwareDict['p'][motor]
    deltaMove = currentPosition - move
    delay = abs(deltaMove) * 0.01
    hardwareDict['p'][motor] = 't'
    await asyncio.sleep(delay)
    hardwareDict['p'][motor] = move


# relative move the collimator motors by setting state to t, waiting,
# then setting to final position
async def move_rel(motor, move):
    currentPosition = hardwareDict['p'][motor]
    finalPosition = currentPosition + move
    hardwareDict['p'][motor] = 't'
    delay = abs(move) * 0.01
    await asyncio.sleep(delay)
    hardwareDict['p'][motor] = finalPosition


# parses the message to figure out what to do
async def check_data(msg):
    loop = asyncio.get_running_loop()
    verb = msg[0]

    if verb in verbDict:        # Check if the verb is valid
        if verb == 'R':
            return ''

        obj = msg[1]
        objList = verbDict[verb]

        if obj in objList:      # Check if the object is valid for the given verb
            if msg[-1:] == '\n':
                rem = msg[2:-2]     # Get the remainder of the message minus \r\n
            elif msg[-1:] == '\r':
                rem = msg[2:-1]  # Get the remainder of the message minus \r
            else:
                return "$S2ERR*24"

            if verb == 'M':      # Check if verb is abs move
                try:
                    move = int(rem)
                    if obj == 'p':
                        taskA = asyncio.create_task(move_abs('a', move))
                        taskB = asyncio.create_task(move_abs('b', move))
                        taskC = asyncio.create_task(move_abs('c', move))
                        await asyncio.gather(taskA, taskB, taskC)

                    else:
                        await move_abs(obj, move)

                except:
                    return "$S2ERR*24"

            elif verb == 'm':      # Check if verb is rel move
                try:
                    move = int(rem)
                    if obj == 'p':
                        taskA = asyncio.create_task(move_rel('a', move))
                        taskB = asyncio.create_task(move_rel('b', move))
                        taskC = asyncio.create_task(move_rel('c', move))
                        await asyncio.gather(taskA, taskB, taskC)

                    else:
                        await move_rel(obj, move)

                except:
                    return "$S2ERR*24"

            elif verb == 's':                   # Check if verb is set time
                try:
                    # Ensure DATETIME format
                    hardwareDict['t'] = rem
                except:
                    return "$S2ERR*24"

            elif rem == '':
                if verb == 'o' or verb == 'c':    # Check if verb is open/close
                    if obj == 'b':
                        taskL = asyncio.create_task(open_close(verb, 'l'))
                        taskR = asyncio.create_task(open_close(verb, 'r'))
                        await asyncio.gather(taskL, taskR)

                    else:
                        task = asyncio.create_task(open_close(verb, obj))
                        await asyncio.gather(task)

                elif verb == 'e':                   # Check if verb is expose
                    # Depending on object, go through expose routine
                    return ''

                elif verb == 'r':                   # Check if verb is report
                    if obj == 'B':
                        btm = hardwareDict['B']
                        tmpReply = f"S2BTM,{btm}"

                    elif obj == 'a' or obj == 'b' or obj == 'c':
                        mra = hardwareDict[obj]
                        tmpReply = f"S2MRA,{mra}"

                    elif obj == 'e':
                        envT0 = hardwareDict[obj]['T0']
                        envT1 = hardwareDict[obj]['T1']
                        envT2 = hardwareDict[obj]['T2']
                        envT3 = hardwareDict[obj]['T3']
                        envH0 = hardwareDict[obj]['H0']
                        envH1 = hardwareDict[obj]['H1']
                        envH2 = hardwareDict[obj]['H2']
                        envH3 = hardwareDict[obj]['H3']
                        tmpReply = f"S2ENV,{envT0}C,{envH0}%,0,{envT1}C,{envH1}%,1," \
                                   f"{envT2}C,{envH2}%,2,{envT3}C,{envH3}%,3"

                    elif obj == 'i':
                        rION = hardwareDict[obj]['r']
                        bION = hardwareDict[obj]['b']
                        tmpReply = f"S2ION,{rION},r,{bION},b"

                    elif obj == 'o':
                        xACC = hardwareDict[obj]['x']
                        yACC = hardwareDict[obj]['y']
                        zACC = hardwareDict[obj]['z']
                        tmpReply = f"S2ACC,{xACC},{yACC},{zACC}"

                    elif obj == 'p':
                        sPNU = hardwareDict[obj]['s']
                        lPNU = hardwareDict[obj]['l']
                        rPNU = hardwareDict[obj]['r']
                        pPNU = hardwareDict[obj]['p']
                        tmpReply = f"S2PNU,{sPNU},s,{lPNU},l,{rPNU},r,{pPNU},p"

                    elif obj == 's':
                        sSHT = hardwareDict['s']
                        tmpReply = f"S2SHT,{sSHT}"

                    elif obj == 't':
                        tTIM = hardwareDict['t']
                        tmpReply = f"S2TIM,{tTIM}"

                    elif obj == 'v':
                        vVER = hardwareDict['v']
                        tmpReply = f"S2VER,{vVER}"

                    else:
                        return "$S2ERR*24"

                    return add_checksum(tmpReply)

                else:
                    return "$S2ERR*24"
            else:
                return "$S2ERR*24"
        else:
            return "$S2ERR*24"
    else:
        return "$S2ERR*24"

    return ''


async def handle_data(reader, writer):
    data = await reader.read(100)
    message = data.decode()
    addr = writer.get_extra_info('peername')

    print(f"Received {message!r} from {addr!r}")

    reply = await check_data(message)

    reply = reply + '\r\n>'
    print(f"Send: {reply!r}")
    writer.write(reply.encode())
    await writer.drain()
    writer.close()


async def main():
    server = await asyncio.start_server(handle_data, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    print(f"Serving on {addr}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    hardwareDict['B'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime())
    asyncio.run(main())
