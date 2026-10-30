# Dataset card: helmet detection

## Sources
Public: Roboflow "Hard Hat Workers" dataset (public domain), about 7,000 images with boxes for helmet, head and person. Client: 1,200 site images labeled by our annotation team in the same format.

## Classes (current annotation guide v1)
helmet: any helmet visible in the image. head: a head without a helmet. person: a full person.

## Label statistics
About 21,000 helmet boxes, 6,500 head boxes. In a sample review of 400 images, 9% of helmet boxes were helmets NOT on a head (held in hand, clipped to a belt, lying on a table).

## Annotation format
YOLO text files: one line per box with class id and normalized x, y, width, height.
