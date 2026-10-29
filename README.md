# Armando Description

ROS 2 description and Gazebo simulation package for the Armando manipulator.
The package includes the robot model, controller configuration, a workbench
world, two simulated cameras, and a keyboard teleoperation node.

This package can remain inside a larger Git repository. Run the ROS commands
below inside the Docker container that contains ROS and the modified workspace.
Gazebo and rqt require a working graphical display connection from the container.

## Requirements

- ROS 2 Humble and `colcon`.
- A compatible Gazebo / `ros_gz` / `gz_ros2_control` installation.
- Dependencies declared in `package.xml`, including `aruco_ros`.
- Python 3 with `rclpy`, `sensor_msgs`, and `trajectory_msgs`.
- `rqt_image_view` for camera validation; RViz for frame inspection.

The development environment exposes Gazebo Transport through `ign topic`.
Environments using the newer CLI naming can use `gz topic` instead. Comments
mentioning Harmonic in the existing launch file do not identify the Gazebo
version actually installed in the container.

## Package layout

| Path | Purpose |
| --- | --- |
| `urdf/arm.urdf.xacro` | Main robot description assembled by the launch file. |
| `urdf/armando_body.urdf.xacro` | Robot links, joints, materials, and control configuration. |
| `urdf/armando_camera.urdf.xacro` | Fixed and wrist camera descriptions. |
| `launch/armando_gazebo.launch.py` | Simulation, robot spawning, controllers, bridges, and marker detection. |
| `scripts/armando_keyboard_teleop.py` | Keyboard teleoperation node. |
| `config/` | Controller configuration. |
| `worlds/`, `models/`, `meshes/` | Simulation world and robot assets. |

## Install dependencies and build

The examples assume the workspace is `~/ros2_ws`. Keep the package in its
existing location under `src`; it does not need to be moved out of its parent
repository.

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws

# Locate the package, including when it is nested inside another repository.
colcon list --packages-select armando_description
PKG_SRC="$(colcon list --packages-select armando_description --paths-only)"

sudo apt update
rosdep update
rosdep install --from-paths "$PKG_SRC" --ignore-src -r -y

# Viewer used for the camera tests.
sudo apt install ros-humble-rqt-image-view

colcon build --packages-select armando_description --symlink-install
source install/setup.bash

ros2 pkg executables armando_description
```

The executable list must include:

```text
armando_description armando_keyboard_teleop
```

If the project requires additional underlays built from source, source them
before building this package. If APT cannot locate a ROS dependency, check
`sudo apt update` errors, the ROS repository configuration, and compatibility
with the container's Ubuntu release before continuing.

### Clean-build validation

Use fresh build and install directories to verify that the executable does not
depend on files left over from an earlier build:

```bash
source /opt/ros/humble/setup.bash
cd ~/ros2_ws

colcon --log-base log_camera_teleop_clean build \
  --build-base build_camera_teleop_clean \
  --install-base install_camera_teleop_clean \
  --packages-select armando_description \
  --symlink-install

source install_camera_teleop_clean/setup.bash
ros2 pkg executables armando_description
```

These directory names must be unused for a clean test. Choose new names when
repeating the test. For the remaining commands, source
`~/ros2_ws/install_camera_teleop_clean/setup.bash` instead of the normal
`~/ros2_ws/install/setup.bash` if testing this clean installation. Use the same
installation in every terminal.

## Start the simulation

Open a terminal inside the container:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 launch armando_description armando_gazebo.launch.py
```

Leave this terminal open and wait for Gazebo, the robot, and the controllers
to start. In another terminal in the same container:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 control list_controllers
ros2 topic echo /joint_states --once
```

Both `joint_state_broadcaster` and `joint_trajectory_controller` should be
active, and `/joint_states` should contain the arm joints `j0` through `j3`.

## Camera design

The two cameras serve different purposes:

| Camera | Attachment | ROS image topic | ROS camera information |
| --- | --- | --- | --- |
| Fixed camera | `base_link` through `camera_mount` | `/camera/image_raw` | `/camera/camera_info` |
| Wrist camera | `crawer_base` through `wrist_camera_joint` | `/wrist_camera/image` | `/wrist_camera/camera_info` |

The fixed camera is mounted one metre along the base frame's Z axis. Its
visual box can appear suspended because no physical support is drawn.

The wrist camera uses the following mounting transform relative to
`crawer_base`:

```xml
<origin xyz="0.0 0.0 0.04" rpy="0 -1.57079632679 0"/>
```

The camera is placed 4 cm along the gripper's local Z axis. The rotation aligns
the sensor's viewing direction, its local +X, with the gripper's +Z approach
direction. The separate optical frame uses:

```xml
<origin xyz="0 0 0" rpy="-1.57079632679 0 -1.57079632679"/>
```

This defines optical axes with Z forward, X right, and Y down. It changes the
coordinate convention, not the physical mounting. Both joints are fixed:
the camera and its optical frame move together with the gripper.

The Gazebo sensor block generates images; the visual box alone does not.
Separate bridge entries forward the wrist image and camera information into
ROS without changing the fixed camera topics.

## Validate both cameras

With the simulation running, list Gazebo Transport topics:

```bash
ign topic -l
# If your environment uses the newer CLI name instead:
# gz topic -l
```

Expected camera topics in Gazebo:

```text
/camera
/camera_info
/wrist_camera/image
/wrist_camera/camera_info
```

Verify ROS receives the data:

```bash
ros2 topic list
ros2 topic hz /wrist_camera/image
```

Stop the frequency measurement with Ctrl+C, then inspect the camera information:

```bash
ros2 topic echo /wrist_camera/camera_info --once
```

Check that the camera information contains image dimensions and calibration
matrices. Check that image and camera information headers identify the wrist
optical frame:

```bash
ros2 topic echo /wrist_camera/image --field header --once
ros2 topic echo /wrist_camera/camera_info --field header --once
```

The expected frame is `wrist_camera_optical_frame`. If another frame is
reported, check support for `gz_frame_id` in the installed Gazebo version and
the bridge's frame configuration.

Open the two viewers in separate terminals after sourcing ROS and the workspace:

```bash
ros2 run rqt_image_view rqt_image_view /camera/image_raw
```

```bash
ros2 run rqt_image_view rqt_image_view /wrist_camera/image
```

Optional frame inspection:

```bash
ros2 run rviz2 rviz2
```

Set the Fixed Frame to `base_link` and add TF and RobotModel displays. For
RobotModel, select `/robot_description` as the description topic; use
Transient Local durability if needed. Display `crawer_base` and
`wrist_camera_optical_frame`. Their blue +Z axes must be parallel and point
beyond the fingertips.

## Keyboard teleoperation

In a third terminal in the same container:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
ros2 run armando_description armando_keyboard_teleop
```

Wait for `Posizioni ricevute. Tastiera pronta.` Keep keyboard focus on this
terminal while observing the image viewer. No Enter key is required.

| Increase | Decrease | Joint |
| --- | --- | --- |
| `q` | `a` | `j0` |
| `w` | `s` | `j1` |
| `e` | `d` | `j2` |
| `r` | `f` | `j3` |

Each key event changes the target by 0.05 rad, approximately 2.9 degrees,
with a requested trajectory duration of 0.5 seconds. Holding a key uses the
terminal's key-repeat behavior. Esc or Ctrl+C exits; the controller may still
complete the last target already sent. Arrow keys are not supported.

The node reads `/joint_states` before accepting motion commands and maps
positions by joint name. It publishes all four joint targets on
`/joint_trajectory_controller/joint_trajectory`. Targets are limited to the
URDF range of -3.14 to +3.14 rad and to 0.15 rad ahead of the measured joint
position. New commands are rejected if feedback is older than one second or
no subscriber is connected. This is joint-space teleoperation without
collision-avoiding motion planning.

`CMakeLists.txt` installs the script under `lib/armando_description`, renaming
it to `armando_keyboard_teleop`. `package.xml` declares its runtime
dependencies. No manual copy into `install/` is required.

### End-to-end validation

1. Verify `ros2 run armando_description armando_keyboard_teleop` works after
   the clean build described above.
2. With the wrist viewer open, use a few `w` / `s` key presses and verify that
   the arm and wrist image change together. Test the remaining joint pairs.
3. Verify that the fixed camera retains its pose relative to the base. Its
   image may still change as the moving robot enters its field of view.
4. Bring a visible target into the wrist camera's viewing direction and
   capture the image together with the robot pose in Gazebo. A cube on the
   workbench can be used once the gripper is directed towards it. With the
   arm upright, the camera points upward and may see only the background and
   the fixed camera's red visual box.

