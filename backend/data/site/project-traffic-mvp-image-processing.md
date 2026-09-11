---
title: "Traffic MVP: Computer Vision Traffic Analysis"
url: https://youssef-bt.github.io/projects/traffic-mvp-image-processing
---

# Traffic MVP: Computer Vision Traffic Analysis

## Description

Real-time vehicle detection and traffic flow analysis using YOLOv8 and OpenCV. Processes video streams, counts vehicles, exports metrics to CSV, and provides a Streamlit dashboard for visualization.

## Project facts

**Role:** Computer Vision Engineer

**Company:** Personal Project

**Period:** 2026-01

**Location:** Morocco

**GitHub:** https://github.com/YOUSSEF-BT/traffic-mvp-image-processing

## Tags

- Python
- OpenCV
- YOLOv8
- Computer Vision
- Streamlit
- Traffic Analysis

## Solution

Built a complete traffic analysis pipeline leveraging YOLOv8 for object detection and OpenCV for video processing. The system detects and tracks vehicles in real-time, generates detailed CSV reports, and includes a Streamlit dashboard for interactive data visualization.

## Key achievements

- High accuracy vehicle detection using YOLOv8
- Real-time processing with visual overlays
- Comprehensive metrics export (time, count, speed, congestion)
- User-friendly Streamlit dashboard for exploration
- Easy configuration via YAML

## Technology stack

- Python 3
- OpenCV
- Ultralytics YOLOv8
- Streamlit
- Pandas
- NumPy
- FFmpeg

## Results

- **detection:** Real-time YOLOv8
- **fps:** 30+ FPS on CPU
- **export:** CSV with metrics
- **dashboard:** Streamlit

## Limitations

- Speed estimation is approximate without camera calibration
- False positives may occur with poor video quality or unusual angles
- Single-video processing; multi-camera not yet implemented

## Future improvements

- Camera calibration for accurate speed measurement
- Multi-object tracking (DeepSORT/ByteTrack)
- ROI-based counting (virtual lines)
- Reduce false positives with better filtering
- Multi-camera support
- Deploy dashboard to Streamlit Cloud

## Source provenance

Generated from `src/data/projects/trafficMVP.js` in the public portfolio repository. The portfolio source is authoritative for this generated document.

