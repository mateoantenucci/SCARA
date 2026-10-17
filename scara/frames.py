"""Transformaciones rígidas en metros; columnas de ejes y última columna posición."""

import math


def multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def transform_point(matrix, point):
    return [sum(matrix[i][j] * point[j] for j in range(3)) + matrix[i][3] for i in range(3)]


def rigid_inverse(matrix):
    rotation = [[matrix[j][i] for j in range(3)] for i in range(3)]
    return [row + [-sum(row[j] * matrix[j][3] for j in range(3))] for row in rotation] + [[0, 0, 0, 1]]


def z_pose(position=(0, 0, 0), angle=0):
    c, s = math.cos(angle), math.sin(angle)
    return [[c, -s, 0, position[0]], [s, c, 0, position[1]],
            [0, 0, 1, position[2]], [0, 0, 0, 1]]


def chain_frames(q, config):
    """Marcos de los cinco cuerpos; TOOL coincide con el TCP provisional."""
    g = config["geometry"]
    base = z_pose()
    arm = z_pose([0, 0, g["shoulder_z"]], q[0])
    forearm = multiply(arm, z_pose([g["l1"], 0, g["elbow_z_offset"]], q[1]))
    wrist = multiply(forearm, z_pose([g["l2"], 0, 0], q[2]))
    tool = multiply(wrist, z_pose([0, 0, g["tool_z_offset"] - q[3]]))
    return dict(base=base, arm=arm, forearm=forearm, wrist=wrist, tool=tool)
