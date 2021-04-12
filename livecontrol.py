''' Control 4 EV3 motors live using keyboard on-the-fly
1234QWER for movements forward, and ASDFZXCV for back
, and . for increasing or decreasing speed
'''

import mindctrl
import msvcrt

keyboard = {b'1':(0, 5),
      b'2':(1, 5),
      b'3':(2, 5),
      b'4':(3, 5),
      b'q':(0, 1),
      b'w':(1, 1),
      b'e':(2, 1),
      b'r':(3, 1),
      b'a':(0, -1),
      b's':(1, -1),
      b'd':(2, -1),
      b'f':(3, -1),
      b'z':(0, -5),
      b'x':(1, -5),
      b'c':(2, -5),
      b'v':(3, -5)}

def livecontrol(port = 'COM8', rotspeed = 100, step = 10):
    # Initiate connection
    print('Opening connection to EV3')
    ev3 = mindctrl.EV3('COM8')
    print('Controlling EV3 live at port ' + port)
    print('Press one of keys: 1234QWERASDFZXCV[]-= or Esc')

    while ...:
        code = 0

        while not code: code = msvcrt.kbhit()  # Wait for a key
        code = msvcrt.getch()

        if code in keyboard.keys():
            # Pressed a movement key
            motor = keyboard[code][0]
            amount = keyboard[code][1] * step
            print('Motor ', motor + 1, ', ', amount, 'deg', sep = '')
            matrix = [0, 0, 0, 0]
            matrix[motor] = amount
            # Rotate
            ev3.rotate(matrix[0], matrix[1], matrix[2], matrix[3], speed = rotspeed)

        if code == b'\x1b':
            # Esc
            # Close EV3 connection
            print('Closing connection')
            ev3.disconnect()
            break

        if code == b'[':
            rotspeed -= 10
            if rotspeed < 10: rotspeed = 10
            print('Rotation speed', rotspeed)

        if code == b']':
            rotspeed += 10
            if rotspeed > 100: rotspeed = 100
            print('Rotation speed', rotspeed)

        if code == b'-':
            step -= 5
            print('Step', step)

        if code == b'=':
            step += 5
            print('Step', step)

print('Done')


# ------------------
# Start self if main
if __name__ == '__main__':
    livecontrol()