'''
MindControl v1.3

Requires PySerial (as the Bluetooth is used only as a transmitter for
standard serial port profiles). You can simply install it using:
pip install pyserial

You can freely use MindControl whatever way you wish,
and distribute it as much as you like, either standalone
or as a component of your other projects. However, you may
not sell it as such, and please keep Legoism.info credited.
MindControl is provided as-is, I hold no responsibility to
any kind of damage you may have done to anything or anyone
by using MindControl or any of its derivatives. For any
unclarities, Apache License 2.0 applies.

Thanks to Thiago Marzagao for providing ev3py, the spiritual
predecessor of MindControl! :)

And visit KOCKICE, www.kockice.hr, the underlying LUG

v1.0 - Initial version
v1.1 - Safe rounding of received floating-point numbers to integers
v1.2 - "Stepper" proportional motor movements list generator added
v1.3 - Added music generation sequence function (melody)
'''

# Inits

import datetime
import struct
import time

# General settings
# ================

logtofile = True  # Write to mindctrl.log
logtoconsole = True  # Write to console
betweendelay = 0  # Delay between movements (in seconds)

# Peripheral functions & constants
# ================================

# Pack values into bytes (EV3-specific)


def pack1b(value):  # One direct byte constant (LC0)
    return bytes((round(value),))  # Float-safe


def pack2b(value):  # Two-byte constant (LC1)
    b1 = 129
    b2 = round(value) & 255  # Float-safe
    return bytes((b1, b2))


def pack3b(value):  # Three-byte constant (LC2)
    value = round(value)  # Float-safe
    b1 = 130
    b2 = value & 255
    b3 = (value >> 8) & 255
    return bytes((b1, b2, b3))


def pack5b(value):  # Five-byte constant (LC4)
    value = round(value)  # Float-safe
    b1 = 131
    b2 = value & 255
    b3 = (value >> 8) & 255
    b4 = (value >> 16) & 255
    b5 = (value >> 24) & 255
    return bytes((b1, b2, b3, b4, b5))

# Logging stuff


def addlog(logline):
    if logtoconsole: print(logline)
    if logtofile:
        logline = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S, ') + \
            str(logline)
        logfile = open('mindctrl.log', 'a', encoding='utf8')
        logfile.write(logline + '\n')
        logfile.close()

# Delay between movements


def delaymove():
    if betweendelay > 0:
        addlog('Delay: ' + str(betweendelay))
        time.sleep(betweendelay)


# Color catalog for the EV3 color-mode (mode 2) detection
ev3colorsensor = {0: 'NONE', 1: 'BLACK', 2: 'BLUE', 3: 'GREEN',
                  4: 'YELLOW', 5: 'RED', 6: 'WHITE', 7: 'BROWN'}


# User functions
# ==============

# For rotating multiple motors simultaneously, each by specified precise total
# angle, but splitting the total movement to a number of substeps
# where each motor does only a little part of the movement. These substeps
# are performed simultaneously each, and the full angle extent of each
# is determined by the step that the longest-spinning motor has to make.
# The purpose is to split generally very accurate simultaneous movements
# into plenty of small, but well-controlled sub-movements.
# The point is, instead of rotating the motors directly, to return a list
# of independent movements because the user may want to split the movements
# on multiple devices, perform additional operations between each step, etc.
# Always adapt the size of "start", if provided, to size of the "end" which
# is mandatory. And return only integers in the lists (list of lists).
# It is not limited to 4 or 7 motors but works with any sensible size.
# If only one list supplied, it's treated as 'end', and if two, they are
# treated as 'start' and 'end'.
def getstepper(*lists):

    # Parse whether only end was supplied, or both start and end
    if len(lists) == 2:  # Star and end supplied
        start = lists[0]
        end = lists[1]
    else:  # Just end supplied, assume all start from zero
        start = [0]
        end = lists[0]

    # Resize start according to end
    start = [val if val is not None else 0 for val in start]
    start = start[0:len(end)]
    start = start + [0] * (len(end) - len(start))

    # Normalize end
    end = [val if val is not None else 0 for val in end]

    # Get precalculating
    motors = len(end)
    delta = [end[m] - start[m] for m in range(motors)]
    steps = max([abs(v) for v in delta])
    increment = [delta[m] / steps for m in range(motors)]
    aggregator = [start]  # Start is not included later - do it now

    # Iterate
    for step in range(steps):
        start = [start[m] + increment[m] for m in range(motors)]
        # This epsilon addition is here to avoid rounding to the
        # nearest even number, which in this case yields some
        # unwanted effects.
        aggregator.append([round(v + 1e-10) for v in start])

    return aggregator


# Convert a given musical melody to a list of successive notes, with each having its frequency,
# duration, and volume. Pauses are treated like any notes played with zero volume. General syntax:
# c,c#,d,d#,e,f,f#,g,g#,a,b,h - notes
# c#3, f4, b2 - octaves of notes (if not specified, last used is applied)
# c#3/2, g/4, b/3 - lengths of notes (if not specified, last used is applied)
# PPP, PP, P, MP, MF, F, FF, FFF - dynamics from this point on
# r/1, r/2, r/4 - rests with specified lengths
# T67, T123 - tempo in BPM from now on
# Separate notes with spaces. Example:
# melody('T120 MF c3/2 g/2 d/2 a/2 FF e/1')
# Note that case sensitivity is important, to distinguish between an 'f' note and forte dynamics
def melody(notes):

    # Set some defaults and constants
    names = ['c#', 'c', 'd#', 'd', 'e', 'f#', 'f', 'g#', 'g', 'a', 'b', 'h']
    volumes = {'PPP': 12, 'PP': 24, 'P': 37, 'MP': 50,
               'MF': 62, 'F': 75, 'FF': 87, 'FFF': 100}
    halftone = 2 ** (1 / 12)
    volume = 50  # Mezzoforte (MF)
    tempo = 120  # Standard tempo is 120 BPM
    currentoctave = 4  # Standard is the 4th octave
    currentlength = 4  # Standard is a quarter note

    # Firstly get the tone frequency list
    # Assume standard: A4=440Hz
    freqs = {}
    for tone in range(97):
        octave = tone // 12
        name = names[tone % 12]  # Tones repeat each 12th
        offset = tone - 57  # Because A4 is 57th in this sequence
        freq = 440 * (halftone ** offset)  # Frequency get from halftone product
        freqs[name + str(octave)] = freq

    # Clean & separate the note sequence
    while '  ' in notes: notes = notes.replace('  ', ' ')
    notes = notes.split(' ')

    aggregator = []  # Final notes aggregator

    for note in notes:
        # Process each one

        if note in volumes.keys():  # Dynamics
            volume = volumes[note]

        if note[0] == 'T':  # Tempo
            tempo = int(note[1:])

        for cn in names:  # Note
            if note.startswith(cn):
                # Found note cn
                specs = note[len(cn):]
                # Get octave
                poct = specs.partition('/')[0]
                if poct: currentoctave = int(poct)
                # Get length
                nlen = specs.partition('/')[2]
                if nlen: currentlength = int(nlen)
                notduration = (120 / tempo) / currentlength

                # Build note name
                notname = cn + str(currentoctave)
                # Get frequency
                notfreq = freqs[notname]

                # Aggregate everything
                aggregator.append([notfreq, notduration, volume])

                break  # Not to detect "shorter notes"

        if note[0] == 'r':  # Rest
            # Just length matters
            nlen = note.partition('/')[2]
            if not nlen:
                restduration = currentlength
            else:
                restduration = int(nlen)
            restduration = (120 / tempo) / restduration

            # Add final
            aggregator.append([440, restduration, 0])

    # All notes generated; finished
    return aggregator


# Master EV3 class
# ================

class EV3:

    # Establish a connection
    def __init__(self, conn='COM8', baudrate=28800, timeout=15):
        import serial
        addlog('Opening EV3 port...')
        if conn!='TEST':
            self.port = serial.Serial(conn, baudrate, timeout=timeout)  # Open at 28800 baud
        addlog('EV3 Port open')

        # Set variables
        self.relposition = [0, 0, 0, 0]  # Positions for relative moves
        self.relscale = [1, 1, 1, 1]  # Relative move scale (default 1: direct)

    # Close a connection (clean end)

    def disconnect(self):
        self.port.close()
        addlog('EV3 Port closed')

    # This is the 'main' rotation instruction.
    # Rotate multiple motors, under given speed (percent), each motor with its
    # own angle, with speeds calculated in-code to make them all stop at as
    # similar time as possible if necessary, or each individually.
    # The supplied speed always applies to the motor that rotates the longest
    # magnitude, and the others are calculated as rounded fractions correlating
    # to their own rotation angles. If not all at once, then they are executed
    # sequentially, as steps of simple rotates.
    # Usage example: rotate(mot1,mot2,mot3,mot4,speed,simult)
    # mot1-4: Absolute angles to turn (in degrees, + or -)
    # speed: Speed to turn with (0..100), percentage
    # simult: Boolean, whether to turn all at once (True) or sequentially (False)
    # Motors that are not specified at the end can be skipped. Those that need
    # to be ignored before others, have to have None or 0 passed as angles.

    def rotate(self, *motors, speed=100, simult=False):
        addlog('EV3 Rotate Abs - Spd:' + str(speed) + ' Simult:' + str(simult) +
               ' Angs:' + ','.join([str(val) for val in motors]))

        # Parse motor data
        if len(motors) > 4:
            # Wrong number of parameters
            addlog('EV3 ERROR: Maximum 4 angle parameters for rotate instruction')
            return None  # Error a priori

        # Normalize input matrix
        motors = list(motors)
        for entry in range(len(motors)):
            if motors[entry] is None: motors[entry] = 0
        motors = motors + [0] * (4 - len(motors))  # Normalize to 4 values

        if simult:
            # Run all motors simultaneously
            # -----------------------------

            # Get maximum angle of any motor (for further calculations)
            maxangle = max([abs(val) for val in motors])

            moves = []  # Aggregator of moves
            for move in enumerate(motors):
                if not move[1]: continue  # Zero-move, nothing to do
                # Build a triplet [Motor byte, angle, rel. calculated speed: minimum 1]
                moves.append([bytes((2 ** move[0],)),
                              move[1],
                              round(abs(speed * move[1] / maxangle)) or 1])

            # Build a multipart message

            header = bytes((0, 0, 0, 0, 0))  # Message number, reply, global variables

            # Body instructions
            body = bytes(0)  # Aggregator of message bytes
            for move in moves:
                # Iterate over each move, consisting of:
                # motor bytes, signed angle, absolute speed

                # Check rotation speed and set polarities accordingly
                if move[1] < 0:
                    # Reverse
                    polarity = bytes((167, 0)) + \
                        move[0] + \
                        bytes((63,))
                else:
                    # Forward
                    polarity = bytes((167, 0)) + \
                        move[0] + \
                        bytes((1,))
                body += polarity

                # Instruction, brick, motors, speed, rampup, hold, rampdown, brake afterwards
                movement = bytes((174, 0)) + \
                    move[0] +  \
                    pack2b(move[2]) +  \
                    pack5b(0) + \
                    pack5b(move[1]) + \
                    pack5b(0) +  \
                    bytes((1,))
                body += movement

            # Wait for completion
            wait = bytes((170, 0, 15))  # Wait for all motors

            # Assemble and send a final message
            message = header + body + wait
            self.send(message)

            # Replied - movement finished. Delay if required
            delaymove()

        else:
            # Run each motor separately (sequentially)
            # ----------------------------------------

            # Iterate over all motors independently
            for motor in enumerate(motors):
                if not motor[1]: continue  # Zero angle - nothing to turn

                motorhex = bytes((2 ** motor[0],))  # Hex code for this motor
                header = bytes((0, 0, 0, 0, 0))  # Message number, reply, global variables

                # Check rotation speed and set polarities accordingly
                if motor[1] < 0:
                    # Reverse
                    polarity = bytes((167, 0)) + \
                        motorhex + \
                        bytes((63,))
                else:
                    # Forward
                    polarity = bytes((167, 0)) + \
                        motorhex + \
                        bytes((1,))

                # Instruction, brick, motors, speed, rampup, hold, rampdown, brake afterwards
                body = bytes((174, 0)) + \
                    motorhex + \
                    pack2b(speed) + \
                    pack5b(0) + \
                    pack5b(motor[1]) + \
                    pack5b(0) + \
                    bytes((1,))

                # Send to begin rotating (not strictly necessary, but proper)
                start = bytes((166, 0)) + motorhex

                # Wait for completion
                wait = bytes((170, 0, 15))  # Wait for all motors

                # Assemble and send a final message
                message = header + polarity + body + start + wait
                self.send(message)

                # Replied - movement finished. Delay if required
                delaymove()

    # Move four motors to specified relative positions - get their desired
    # positions and the desired speed. They all turn at the same time, i.e.
    # utilize the rotate function. Format is for each motor sequentially:
    # rotateto(mot1,mot2,mot3,mot4,speed=100)

    def rotateto(self, *relpos, speed=100, simult=False):
        addlog('EV3 Rotate Rel - Spd:' + str(speed) + ' Simult:' + str(simult) +
               ' Pos:' + ','.join([str(val) for val in relpos]))

        # Parse motor data
        if len(relpos) > 4:
            # Wrong number of parameters
            addlog('EV3 ERROR: Maximum 4 position parameters for rotateto instruction')
            return None  # Error a priori

        # Normalize input matrix
        relpos = list(relpos)
        relpos = relpos + [None] * (4 - len(relpos))  # Normalize to 4 values

        deltas = []  # Aggregator of 'differences' for the motors to make

        # Iterate through all four motors
        for motor in enumerate(relpos):
            if motor[1] is None:
                deltas.append(0)  # Nothing to do
                continue

            # Value was specified
            delta = motor[1] - self.relposition[motor[0]]  # Get difference
            delta = delta * self.relscale[motor[0]]  # Multiply by scale
            deltas.append(delta)
            self.relposition[motor[0]] = motor[1]  # Update relative position

        # Perform the actual rotations
        self.rotate(*deltas, speed=speed, simult=simult)

    # Start rotating the motors, without a specified duration or degrees,
    # just keep them running. Supply just the speed for each of the motors,
    # optional, with None supplied where nothing is to be changed. Zero can
    # be supplied to stop a motor or more of them, though that employs a
    # different instruction than the one for spinning (a special case).

    def spin(self, *speeds):
        addlog('EV3 Spin:' + ','.join([str(val) for val in speeds]))

        # Parse motor data
        if len(speeds) > 4:
            # Wrong number of parameters
            addlog('EV3 ERROR: Maximum 4 position parameters for spin instruction')
            return None

        # Normalize input matrix
        speeds = list(speeds)
        speeds = speeds + [None] * (4 - len(speeds))  # Normalize to 4 values

        message = bytes((0, 0, 0, 0, 0))  # Message byte aggregator
        # Iterate through all the motors
        for motor in enumerate(speeds):
            if motor[1] is None: continue  # Nothing to do

            # Value was specified - something to do
            if motor[1] == 0:
                # Stop the motor
                submessage = bytes((163, 0, 2 ** motor[0], 1))
                message = message + submessage
            else:
                # Start rotating the motor
                if motor[1] < 0:  # Polarity
                    submessage = bytes((167, 0, 2 ** motor[0], 63))  # Reverse
                else:
                    submessage = bytes((167, 0, 2 ** motor[0], 1))  # Forward
                submessage = submessage + bytes((165, 0, 2 ** motor[0])) + pack2b(abs(motor[1]))
                submessage = submessage + bytes((166, 0, 2 ** motor[0]))
                message = message + submessage

        # Send aggregated message
        self.send(message)

    # Stop all motors, probably started by spin

    def stop(self):
        addlog('EV3 Stop')
        self.spin(0, 0, 0, 0)

    # Send message to the EV3. Mostly to be used internally, though manual bytes
    # can be supplied as well

    def send(self, message):
        # Calculate length (which does not count itself)
        msglen = bytes((len(message) % 256, len(message) // 256))  # LSB first
        fullmessage = msglen + message

        # Send
        if self.port.isOpen():
            addlog('EV3 Send:' + ','.join([str(e) for e in list(fullmessage)]))
            self.port.write(fullmessage)  # Send message

            # Get reply
            replen = self.port.read(2)  # Two bytes, LSBf size
            replen = replen[0] + replen[1] * 256  # Get numerical value
            reply = self.port.read(replen)  # Read message payload
            addlog('EV3 Receive:' + ','.join([str(e) for e in list(reply)]))
            return reply or None
        else:
            addlog('EV3 ERROR: Port is not open (command cancelled)')
            return None  # Error a priori

    # Universal sensor instruction, i.e. independent from sensor type or mode.
    # Get the sensor numerical value from the given port (ranging from 1 to 4),
    # therefore used as sensor(1). Running in sensor-default mode, i.e. without
    # any mode changes

    def sensor(self, portnum):
        addlog('EV3 Sensor ' + str(portnum))

        # Construct a message
        message = bytes((0, 0, 0, 4, 0, 153, 29, 0, portnum - 1, 0, 0, 1, 96))
        reply = self.send(message)

        # Parse out a reply
        if reply[0:3] != bytes((0, 0, 2)): return None  # Improper reply, error
        if len(reply) != 7: return None  # Improper size, error

        # Unpack bytes
        return struct.unpack('f', reply[3:7])[0]

    # Specific instruction for EV3 color/light sensor which works in multiple
    # modes. Specify a port number being used (1-4) and the desired mode:
    # 0 (or 'reflect'): measuring amount of reflected light
    # 1 (or 'ambient'): measuring amount of ambient light
    # 2 (or 'colors'): detecting a color (if any) under the sensor
    # In mode 0 and 1, returns a number 0-100 (light percentage)
    # In mode 2, returns a detected color number and its name

    def sensor_light(self, portnum, mode):
        addlog('EV3 Color/Light Port:' + str(portnum) + ' Mode:' + str(mode))

        # Check mode (if a string instead of a number)
        if isinstance(mode, str):
            mode = mode.upper()
            if mode.startswith('REFLECT'): mode = 0
            if mode.startswith('AMBIENT'): mode = 1
            if mode.startswith('COLORS') or mode.startswith('COLOURS'): mode = 2

        # Construct and send a message
        message = bytes((0, 0, 0, 4, 0, 153, 29, 0, portnum - 1, 0, mode, 1, 96))
        reply = self.send(message)
        reply = struct.unpack('f', reply[-4:])[0]  # Parse the value out

        # Analyse and return the answer according to the mode
        if mode == 2:
            # Color mode - return the color code along with color name (tuple)
            reply = round(reply)
            reply = (reply, ev3colorsensor[reply])

        return reply

    # Play a sound of a specified frequency, volume and duration.
    # Frequency is in Hz, volume in percentage (1-100) and duration in
    # milliseconds. Control is passed back only after the tone is
    # fully played.

    def tone(self, frequency=440, volume=50, duration=200):
        addlog('EV3 Sound Frequency:' + str(frequency) + 'Hz Volume:' +
               str(volume) + '% Duration:' + str(duration) + 'ms')

        # Construct a message
        message = bytes((0, 0, 0, 0, 0, 148, 1))
        message = message + pack2b(volume)
        message = message + pack3b(frequency)
        message = message + pack3b(duration)
        message = message + bytes((150,))  # Wait until played

        self.send(message)

    # Selftest the EV3 (rotate all motors)

    def selftest():
        addlog('EV3 Self-test started')
        # Rotate all forward and reverse
        self.rotate(90, 180, 270, 360, speed=75, simult=False)
        self.rotate(-450, -450, -450, -450, speed=50, simult=True)
        self.rotate(360, 270, 180, 90, speed=100, simult=False)
        addlog('EV3 Self-test complete')


# Master NXT class
# ================

class NXT:

    # Establish a connection
    def __init__(self, conn='COM4', baudrate=28800, timeout=15):
        import serial
        addlog('Opening NXT port...')
        self.port = serial.Serial(conn, baudrate, timeout=timeout,
                                  parity=serial.PARITY_EVEN)  # Open at 28800 baud
        addlog('NXT Port open')

        # Set variables
        self.relposition = [0, 0, 0]  # Positions for relative moves
        self.relscale = [1, 1, 1]  # Relative move scale (default 1: direct)

    # Start the Mind Control program on the NXT device (if not started)
    # Note that it takes the bytes as the input parameter, and it can be optionally
    # set not to take a 1-second safe delay after starting the program

    def start(self, rxe=b'MindCtrl.rxe', delay=True):
        addlog('Starting MindCtrl.rxe on NXT device')

        # Construct a message
        message = bytes((128, 0)) + rxe + bytes((0,))
        message = bytes((len(message), 0)) + message
        # Send
        self.port.write(message)

        # One-second delay to allow the RXE to start
        if delay: time.sleep(1)

    # Close a connection (clean end)

    def disconnect(self):
        self.port.close()
        addlog('NXT Port closed')

    # Main rotate function. Supply an angle (positive or negative) for each motor or
    # keep zero (or None) for no movement. They are executed in order A-C (1-3).
    # Supplied speed applies to all motors - if various speeds are required, multiple
    # function calls are required.

    def rotate(self, *motors, speed=100):
        addlog('NXT Rotate Abs - Spd:' + str(speed) +
               ' Angs:' + ','.join([str(val) for val in motors]))

        # Parse motor data
        if len(motors) > 3:
            # Wrong number of parameters
            addlog('NXT ERROR: Maximum 3 angle parameters for rotate instruction')
            return None  # Error a priori

        # Normalize input matrix
        motors = list(motors)
        for entry in range(len(motors)):
            if motors[entry] is None: motors[entry] = 0
        motors = motors + [0] * (4 - len(motors))  # Normalize to 4 values

        # Iterate over all motors independently
        for motor in enumerate(motors):
            if not motor[1]: continue  # Zero angle - nothing to turn

            # Construct a message

            # Motor number
            message = bytes([9, 0, 128, 9, 0, 5]) + struct.pack('f', motor[0] + 1) + bytes((0,))
            # Angle
            message += bytes([9, 0, 128, 9, 0, 5]) + struct.pack('f', motor[1]) + bytes((0,))
            # Speed (Power in NXT)
            message += bytes([9, 0, 128, 9, 0, 5]) + struct.pack('f', speed) + bytes((0,))
            # Send to device
            addlog('NXT Send:' + ','.join([str(e) for e in list(message)]))
            self.port.write(message)  # Send message

            # Read the reply
            checkmailbox = bytes([5, 0, 0, 19, 10, 0, 1])  # Check mailbox instruction
            replywaits = 0  # Counter of checked replies

            while True:  # Repeat checking mailbox until 'ACKNOWLEDGED' received
                self.port.write(checkmailbox)

                # Check incoming size
                replysize = self.port.read(2)
                replysize = replysize[0] + replysize[1] * 256
                # Get that number of bytes
                reply = self.port.read(replysize)
                replywaits += 1

                # Check if rejected
                if reply[0:3] == bytes((2, 19, 236)):
                    addlog('NXT ERROR: MindCtrl not started on the device:' +
                           ','.join([str(e) for e in list(reply) if e]))
                    return None  # Error a priori

                # Check if acknowledgement received
                if b'ACKNOWLEDGED' in reply:
                    addlog('NXT Acknowledged in Msg:' + str(replywaits))
                    break

            # Replied - movement finished. Delay if required
            delaymove()

    # Move three motors to specified relative positions - get their desired
    # positions and the desired speed. They all turn sequentially. Usage:
    # rotateto(mot1,mot2,mot3,speed=100)

    def rotateto(self, *relpos, speed=100):
        addlog('NXT Rotate Rel - Spd:' + str(speed) +
               ' Pos:' + ','.join([str(val) for val in relpos]))

        # Parse motor data
        if len(relpos) > 3:
            # Wrong number of parameters
            addlog('NXT ERROR: Maximum 3 position parameters for rotateto instruction')
            return None  # Error a priori

        # Normalize input matrix
        relpos = list(relpos)
        relpos = relpos + [None] * (3 - len(relpos))  # Normalize to 3 values

        deltas = []  # Aggregator of 'differences' for the motors to make

        # Iterate through all four motors
        for motor in enumerate(relpos):
            if motor[1] is None:
                deltas.append(0)  # Nothing to do
                continue

            # Value was specified
            delta = motor[1] - self.relposition[motor[0]]  # Get difference
            delta = delta * self.relscale[motor[0]]  # Multiply by scale
            deltas.append(delta)
            self.relposition[motor[0]] = motor[1]  # Update relative position

        # Perform the actual rotations
        self.rotate(*deltas, speed=speed)

    # Selftest the NXT (rotate all motors)

    def selftest():
        addlog('NXT Self-test started')
        # Rotate all forward and reverse
        self.rotate(90, 180, 270, speed=75)
        self.rotate(-450, -450, -450, speed=50)
        self.rotate(360, 270, 180, speed=100)
        addlog('EV3 Self-test completed')


# Self-test if started as a __main__
if __name__ == '__main__':
    print(list(pack2b(75)))
    print(list(pack5b(540)))

    ev3device = EV3('TEST')

    # ev3device.rotate(None, None, 45)

    ev3device.rotate(None, 540, speed=75)

    # gfx
    # screen is 178x128 px
    '''0 background, 1 foreground color'''
    # ev3device.send(bytes([0, 0, 0, 0, 0,
    #                 132, 9, 1,
    #                 129, 10, 129, 10, 129, 60, 129, 70]))  # Draw
    # # ev3device.send((0,0,0,0,0,132,0)) # Refresh

    # for posit in getstepper([-180, -90]):
    #    ev3device.rotateto(posit[0], posit[1], simult = True, speed = 50)
    # ev3device.rotate(-360, -360,speed=25,simult=True)
    # ev3device.rotate(-720, -280,speed=25,simult=True)
    # ev3device.rotate(-260,-260,speed=25,simult=True)
    # print(ev3device.sensor_light(1,1))
    # ev3device.sensor_light(2,2)
    ev3device.disconnect()
