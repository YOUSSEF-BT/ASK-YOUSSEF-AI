---
title: "Real-Time Road Accident Detection — Computer Vision & Deep Learning"
url: https://youssef-bt.github.io/projects/real-time-road-accident-detection
---

# Real-Time Road Accident Detection — Computer Vision & Deep Learning

## Description

A hybrid real-time road-safety system that combines YOLOv11 vehicle detection, BoT-SORT tracking, a fine-tuned YOLOv11s accident classifier, and αβγ behavioral analysis to trigger alerts and automatically save MP4 evidence clips with CSV event logs.

## Project Facts

**Role:** Computer Vision & AI Engineer

**Company:** NEXTRONIC — ABA Technology

**Period:** February–August 2026

**Location:** Casablanca, Morocco

**Status:** PFE Prototype

**GitHub:** https://github.com/YOUSSEF-BT/Real-time-vision-accident-detection

## Tags

- Computer Vision
- Deep Learning
- YOLOv11
- BoT-SORT
- OpenCV
- Road Safety

## Solution

YOLOv11n first detects road vehicles, while BoT-SORT assigns stable IDs and maintains a 90-frame trajectory history. A fine-tuned YOLOv11s model estimates visual accident confidence in parallel with αβγ behavioral analysis. The decision engine uses the maximum of both scores, applies 0.6 and 0.8 alert thresholds, displays the accident overlay, saves the associated MP4 clip, and writes the event to CSV.

## Key Achievements

- 86.68% precision, 91.56% recall, and 89.06% F1-score on the held-out image test set
- 31.5 FPS measured for the YOLOv11s image inference benchmark
- 12,716 manually annotated images split into 10,192 train, 1,290 validation, and 1,234 test images
- Support for multi-vehicle collisions and abnormal single-vehicle events
- Automatic MP4 evidence clips and CSV logs containing timestamps, IDs, scores, paths, and triggering frames
- Theoretical minimum reaction window of approximately 0.1 seconds at 30 FPS after three confirming frames

## Technology Stack

- Python 3.9+
- Ultralytics YOLOv11
- BoT-SORT
- OpenCV
- NumPy
- Supervision
- PyYAML
- Roboflow
- CSV
- MPS / CUDA

## Results

- **precision:** 86.68%
- **recall:** 91.56%
- **f1Score:** 89.06%
- **inferenceSpeed:** 31.5 FPS
- **datasetSize:** 12,716 images
- **classes:** 2

## Results Context

Metrics above correspond to the YOLOv11s image test benchmark. The complete hybrid video pipeline still requires a fully annotated temporal evaluation set for official end-to-end precision and recall.

## Disclaimer

The published precision, recall, F1-score, and FPS describe the fine-tuned YOLOv11s image test set, not a fully annotated end-to-end video benchmark. Performance can decrease at night, in rain, under heavy occlusion, or with difficult camera angles.

## Limitations

- No official end-to-end video precision and recall without temporal annotations
- Reduced robustness at night, in rain, and under dense occlusion
- Tracker quality remains sensitive to difficult camera angles

## Future Improvements

- Build a temporally annotated unseen-video benchmark
- Expand the dataset with night, rain, occlusion, and hard negatives
- Add stronger ReID support and multi-camera identity continuity
- Optimize the full pipeline for NVIDIA CUDA and edge deployment
- Create a supervision interface for live alerts and evidence review

## Evidence Provenance

Generated from `src/data/projects/accidentDetection.js` in the public portfolio repository. The portfolio source is authoritative for this generated document.
