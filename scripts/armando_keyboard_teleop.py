#!/usr/bin/env python3
"""Teleoperazione dei quattro giunti di Armando da un terminale Linux."""

import math
import select
import sys
import termios
import time
import tty

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


JOINT_NAMES = ['j0', 'j1', 'j2', 'j3']
# Limiti riportati nei tuoi Xacro, espressi in radianti.
LOWER_LIMIT = -3.14
UPPER_LIMIT = 3.14
STEP = 0.05
MOVE_TIME = 0.5
STATE_TIMEOUT = 1.0
# Evita di accumulare una meta molto lontana se si tiene premuto un tasto.
MAX_LEAD = 0.15
KEYS = {
    'q': (0, +1), 'a': (0, -1),
    'w': (1, +1), 's': (1, -1),
    'e': (2, +1), 'd': (2, -1),
    'r': (3, +1), 'f': (3, -1),
}


class ArmandoKeyboardTeleop(Node):
    def __init__(self):
        super().__init__('armando_keyboard_teleop')
        self.positions = None
        self.target = None
        self.last_state_time = None
        self.last_command_time = None
        self.publisher = self.create_publisher(
            JointTrajectory,
            '/joint_trajectory_controller/joint_trajectory',
            10,
        )
        self.subscription = self.create_subscription(
            JointState, '/joint_states', self.on_joint_states,
            qos_profile_sensor_data,
        )
        self.get_logger().info('Attendo /joint_states con j0, j1, j2, j3.')

    def on_joint_states(self, msg):
        # L'ordine in /joint_states puo essere diverso da quello del controller.
        by_name = dict(zip(msg.name, msg.position))
        if not all(name in by_name for name in JOINT_NAMES):
            return
        positions = [float(by_name[name]) for name in JOINT_NAMES]
        if not all(math.isfinite(value) for value in positions):
            return
        first_message = self.positions is None
        self.positions = positions
        self.last_state_time = time.monotonic()
        if first_message:
            self.get_logger().info('Posizioni ricevute. Tastiera pronta.')

    def handle_key(self, key):
        if key not in KEYS:
            return
        now = time.monotonic()
        if self.last_state_time is None or now - self.last_state_time > STATE_TIMEOUT:
            self.target = None
            self.get_logger().warning('Nessuno stato recente: comando non inviato.')
            return
        if self.publisher.get_subscription_count() == 0:
            self.target = None
            self.get_logger().warning('Controller non collegato: comando non inviato.')
            return

        # Al primo tasto e dopo una pausa riparti dalle posizioni misurate.
        if (self.target is None or self.last_command_time is None
                or now - self.last_command_time > STATE_TIMEOUT):
            self.target = self.positions.copy()

        index, direction = KEYS[key]
        value = self.target[index] + direction * STEP
        # Primo limite: distanza dalla posizione effettivamente misurata.
        value = max(self.positions[index] - MAX_LEAD,
                    min(self.positions[index] + MAX_LEAD, value))
        # Secondo limite: corsa del giunto definita nell'URDF.
        self.target[index] = max(LOWER_LIMIT, min(UPPER_LIMIT, value))

        point = JointTrajectoryPoint()
        point.positions = self.target.copy()
        point.time_from_start.sec = int(MOVE_TIME)
        point.time_from_start.nanosec = round((MOVE_TIME % 1) * 1_000_000_000)

        trajectory = JointTrajectory()
        trajectory.joint_names = JOINT_NAMES.copy()
        trajectory.points = [point]
        # Header a zero: il controller interpreta la traiettoria da subito.
        self.publisher.publish(trajectory)
        self.last_command_time = now
        values = ', '.join(f'{value:.2f}' for value in self.target)
        self.get_logger().info(f'Obiettivo [j0, j1, j2, j3]: [{values}] rad')


def run_keyboard(node):
    print('\nTasti: q/a -> j0 | w/s -> j1 | e/d -> j2 | r/f -> j3')
    print('Primo tasto della coppia: +0.05 rad; secondo: -0.05 rad.')
    print('Esc oppure Ctrl+C: esci. La meta gia inviata resta attiva.')
    print('Usa le lettere, non le frecce. Mantieni il focus su questo terminale.\n')
    fd = sys.stdin.fileno()
    saved_settings = termios.tcgetattr(fd)
    try:
        # Legge un tasto senza Invio, mantenendo funzionante Ctrl+C.
        tty.setcbreak(fd)
        while rclpy.ok():
            # Esegue le callback di ROS senza bloccare l'ascolto dei tasti.
            rclpy.spin_once(node, timeout_sec=0.02)
            readable, _, _ = select.select([sys.stdin], [], [], 0.02)
            if readable:
                key = sys.stdin.read(1)
                if key in ('', '\x1b', '\x03'):
                    break
                node.handle_key(key.lower())
    finally:
        # Ripristina il terminale anche in caso di Ctrl+C o eccezione.
        termios.tcsetattr(fd, termios.TCSADRAIN, saved_settings)


def main(args=None):
    if not sys.stdin.isatty():
        print('Avvia questo nodo in un terminale interattivo.', file=sys.stderr)
        return 1
    rclpy.init(args=args)
    node = None
    try:
        node = ArmandoKeyboardTeleop()
        run_keyboard(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
