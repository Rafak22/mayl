# PPE sample images (real, public domain)

Source: Roboflow "Hard Hat Workers" dataset, public domain:
https://public.roboflow.com/object-detection/hard-hat-workers

## How to add the samples (about 10 minutes)
1. Open the link above, sign in with a free Roboflow account, and download the dataset in **YOLOv8** format.
2. Pick **8 images**: 4 with workers wearing helmets correctly, and 4 where a helmet is
   NOT on the head (held in the hand, on a belt, on the ground) or a worker has no helmet.
   The "not on the head" ones are the heart of the bottleneck story.
3. Copy the images into `images/` and their matching `.txt` label files into `labels/`
   (same file name, different extension).
4. Fill `manifest.json` (template below) so the UI knows what each image shows.

Keep images small (resize to ~640 px wide, JPG) so the repo stays light.

## manifest.json template
```json
[
  {"file": "site_01.jpg", "story": "compliant", "note": "Two workers, helmets worn"},
  {"file": "site_05.jpg", "story": "carried_helmet", "note": "Helmet held in the hand: v1 labels call this compliant, the safety officer says violation"}
]
```
Classes in the label files: 0 = head (no helmet), 1 = helmet, 2 = person (check the
dataset's data.yaml, since class order can differ between versions).
