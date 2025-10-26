# Sensor Visualizer

A real-time visualization tool for displaying data from 5 finger-mounted sensors. Shows force and position data on an interactive hand diagram with live graphs.

## Features

- **Hand Overlay**: Visual representation of sensor data overlaid on a hand diagram
- **Force Visualization**: Color-coded circles (green → yellow → red) based on force magnitude
- **Position Arrows**: Real-time directional arrows showing sensor displacement
- **Individual Panels**: Separate visualization for each finger sensor
- **Time Series Graphs**: Real-time plots showing X, Y, Z displacement over time

## Installation

### Requirements
- Python 3.8 or higher
- PyQt5
- pyqtgraph
- pyserial
- numpy

### Quick Setup

1. Clone this repository:
```bash
git clone https://github.com/YOUR_USERNAME/SensorVisualization.git
cd SensorVisualization
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

```bash
python sensor_visualizer.py
```

### Connecting Your Sensors

The application connects to `/dev/ttyACM0` by default at 115200 baud rate.

**Supported Data Formats:**

1. **Flat CSV (15 values)** - All 5 sensors at once:
```
x1,y1,z1,x2,y2,z2,x3,y3,z3,x4,y4,z4,x5,y5,z5
```

2. **Flat CSV with load (20 values)** - All 5 sensors with force values:
```
x1,y1,z1,l1,x2,y2,z2,l2,x3,y3,z3,l3,x4,y4,z4,l4,x5,y5,z5,l5
```

3. **Labeled format** - Individual sensor data:
```
Sensor 1: x,y,z; Sensor 2: x,y,z; Sensor 3: x,y,z; Sensor 4: x,y,z; Sensor 5: x,y,z
```

**Note:** The code automatically calculates force from displacement if not provided.

### Changing Serial Port

To use a different serial port, edit line 435 in `sensor_visualizer.py`:
```python
self._worker = SerialWorker(port='/dev/ttyUSB0')  # Change to your port
```

## Interface

### Tab 1: Hand & Panels
- Left side: Hand diagram with sensor overlays
- Right side: Individual sensor panels showing force (circle) and direction (arrow)

### Tab 2: Time Series
- 5 separate graphs showing X, Y, Z displacement over time
- Last 800 samples displayed
- Real-time scrolling display

## Customizing Finger Positions

The fingertip positions can be adjusted in `sensor_visualizer.py` (lines 209-214):
```python
self._finger_positions_norm: List[QtCore.QPointF] = [
    QtCore.QPointF(0.30, 0.25),  # thumb
    QtCore.QPointF(0.48, 0.12),  # index finger
    QtCore.QPointF(0.63, 0.10),  # middle finger
    QtCore.QPointF(0.76, 0.13),  # ring finger
    QtCore.QPointF(0.86, 0.18),  # pinky
]
```

Values are normalized (0.0 to 1.0) relative to the hand image dimensions.

## Project Structure

```
SensorVisualization/
├── sensor_visualizer.py    # Main application
├── Hand.png               # Hand diagram image
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── .gitignore            # Git ignore rules
```

## Troubleshooting

**Problem:** "Could not open /dev/ttyACM0"
- **Solution:** Make sure your sensor device is connected and you have permission to access it. Try: `sudo chmod 666 /dev/ttyACM0`

**Problem:** Import errors for PyQt5 or pyqtgraph
- **Solution:** Make sure you installed all dependencies: `pip install -r requirements.txt`

**Problem:** Hand.png not found
- **Solution:** Make sure Hand.png is in the same directory as sensor_visualizer.py

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## Author

Created for visualizing multi-sensor finger tracking data.

