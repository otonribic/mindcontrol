#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stewart platform calculations
-----------------------------

Part of Stormpack

Stewart platform is a physical platform with all degrees of movement. It is
controlled by six elongation actuators from below, with each even's actuators
having the common root in the bottom scaffolding, and each odd's actuators
having the common target in the platform itself.

The final effect that any position of a platform both in terms of location and
rotation can be broken down to six lengths of the underlying actuators.

Its drawback, a bit, is the fact that a strictly linear movement or rotation
actually almost always means all six motors need to run coordinatedly and
simultaneously. And even worse, the linear movement from position A to B is
not strictly linear movement of all its motors through all its linear extents
or ranges.

But it is vastly simpler than an X-Y-Z-Az-A-B construction, and due to all
elements compressed, much more resistant to backlash and tolerances as well.

Order of operation:
1) Build a 3D space, X-Y-Z
2) Ascertain a position of the target triangle in 3D space
3) Get its corner points
4) For each corner point, determine two points in the base underneath it
5) Calculate distances to each of those (6 distances altogether, 3x2)

With the assumptions:
1) The base is always at the height zero, and the zeroth actuator is exactly
   right from it, i.e. only moves positive in X axis from the centerpoint.
2) Assume its adjacent root is closer to it, and they are spread around
   in positive direction, i.e. Y negative from the first root.
3) The platform is always above the base.
4) Return values can always be positive floats, or zero, in millimeters.
5) In the submitted values, X-Y-Z displacements are in millimeters, and the
   azimuth, alpha and beta are in degrees. All values are floats with both
   positive and negative values.
6) Assume that the 0,0,0 X-Y-Z value of the platform is actually when it has
   the same center as the frame, i.e. they are right within each other. Any
   height would need to have the Z value positive.
7) Base is always horizontal in the Z plane, i.e. all root points have the Z
   (height) value of 0.
8) If limiter is enabled, if any of the required calculated lengths of the
   actuators is beyond set extents, the function returns None (as an error)
   instead of a 6-item float list.

The millimeters themselves are irrelevant as the scaling works for any unit,
but it is sensible to use some standard unit.

From above, with actuator roots 0-5, and targets a-f:

      2 
    3    cb
     d       1
     e       0
    4    fa
      5
      
Also in this scale, the azimuth is rotating the triangle counterclockwise
if positive, the alpha rotating it along the x-axis, and beta along the y-axis.
Azimuth 0 means that the each platform point is equally far from both its
actuator's roots.

The order of calculation is: offset; azimuth; alpha; beta; X-Y-Z offsets.
"""

import math

# General constants for the platform to be set
# ============================================
# Note that these are supposed to be changed by the user before the first
# invoke.

# Actuator root distance from center on the base [mm]
ACT_ROOT_DISTFC = 120

# Distance between adjacent actuator roots on the base [mm]
ACT_ROOT_ADJDIST = 24

# Actuator target distance from center in the platform [mm]
ACT_TGT_DISTFC = 100

# Distance between adjacent actuator targets in the platform [mm]
ACT_TGT_ADJDIST = 20

# Vertical offset of the platform, i.e. how much it is higher than the
# hypothetical target plane between actuator targets [mm]
TGT_VERT_OFFSET = 16

# Maximum extents of actuators, used for the limiter
ACTUATOR_MIN=80
ACTUATOR_MAX=140

# Calculations
# ============

''' Master function taking into account the X-Y-Z positions, the azimuth
(rotation in Z axis, and alpha/beta, i.e. rotations in X and Y axes
respectively). Returns required actuator lengths for all six of them.
'''
def stewart(xd = 0, yd = 0, zd = 0, azimuth = 0, alpha = 0, beta = 0,
            limiter = False):

    # Convert input angles to radians
    azimuth = azimuth / 180 * math.pi
    alpha = alpha / 180 * math.pi
    beta = beta / 180 * math.pi

    # Firstly determine the position of the actuator roots in the space

    # Get the angle between the adjacent roots (based on right triangles)
    adjrootang = math.atan(ACT_ROOT_ADJDIST / ACT_ROOT_DISTFC / 2)
    adjrootang *= 360 / math.pi

    # Place root points in space
    roots = []  # Master holder of 6x[x,y,z]
    for act in range(6):
        angle = ((act // 2) * 120 + (act % 2) * adjrootang) * math.pi / 180
        roots.append([math.cos(angle) * ACT_ROOT_DISTFC,
                      math.sin(angle) * ACT_ROOT_DISTFC, 0])

    # Loaded to 'roots'. Now calculate the corner points of the platform

    # Determine angle between the adjacent targets (similar to the base)
    adjtgtang = math.atan(ACT_TGT_ADJDIST / ACT_TGT_DISTFC / 2) * 360 / math.pi
    # Determine the angular offset between the base and the platform
    angleoffset = adjrootang / 2 - adjtgtang / 2 - 60

    # Place target points in space
    tgts = []  # Master holder of 6x[x,y,z]
    for act in range(1, 7):
        angle = angleoffset + (act // 2) * 120 + (act % 2) * adjtgtang
        angle *= math.pi / 180
        tgts.append([math.cos(angle) * ACT_TGT_DISTFC,
                     math.sin(angle) * ACT_TGT_DISTFC,
                     - TGT_VERT_OFFSET])

    # First transformation (vertical offset) done. Now perform rotations of the
    # platform target points with the axis at X-Y 0,0

    for order, point in enumerate(tgts):

        # Rotate azimuth, around Z axis
        cx = point[0] * math.cos(azimuth) - point[1] * math.sin(azimuth)
        cy = point[0] * math.sin(azimuth) + point[1] * math.cos(azimuth)
        point[0] = cx
        point[1] = cy

        # Rotate alpha, around X axis
        cy = point[1] * math.cos(alpha) - point[2] * math.sin(alpha)
        cz = point[1] * math.sin(alpha) + point[2] * math.cos(alpha)
        point[1] = cy
        point[2] = cz

        # Rotate beta, around Y axis
        cx = point[0] * math.cos(beta) - point[2] * math.sin(beta)
        cz = point[0] * math.sin(beta) + point[2] * math.cos(beta)
        point[0] = cx
        point[2] = cz

        # Linear X-Y-Z movements at the end
        point[0] += xd
        point[1] += yd
        point[2] += zd

        tgts[order] = point  # Change it in the master list

    # Target points rotated. Now measure distances between them and their roots

    distances = []
    for act in range(6):  # Iterate over actuators

        # Calculate distance between roots and targets
        delta = [roots[act][d] - tgts[act][d] for d in [0, 1, 2]]
        dist = sum([d ** 2 for d in delta]) ** 0.5
        distances.append(dist)
        
    # Check actuator constraints if applicable
    if limiter:
        minimums = [dist < ACTUATOR_MIN for dist in distances]
        maximums = [dist > ACTUATOR_MAX for dist in distances]
        if any(minimums) or any(maximums): return None # Failed

    # Gathered distances, return them
    return distances
    

# Self-test
# =========

if __name__ == '__main__':
    print('Stewart platform actuator calculator, oton.ribic@bug.hr')
    print(stewart(azimuth = 0))