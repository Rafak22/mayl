# Engine contract: alert engine

## Pipeline
Camera image → YOLO model on the site edge box (CPU) → compliance logic → alert to the safety officer's app.

## Compliance logic (current)
A person is compliant if any helmet box is inside the person box. Otherwise an alert is raised.

## Latency
Alert within 60 seconds. Current: 8 seconds end to end.

## Hardware
Edge boxes are CPU-only (Intel NUC class). Models larger than YOLOv8n do not meet latency on all 40 cameras.

## Interfaces
The model outputs boxes with class and confidence. The safety app reads alerts with an image crop and the reason. Changing class names requires an update of the compliance logic and the app's reason text.
