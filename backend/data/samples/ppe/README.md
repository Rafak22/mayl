# PPE sample images

Three photos shown in the Helmet Compliance project's Data & solution tab, one for each case
of the bottleneck story.

| File | Shows |
|---|---|
| `images/site-compliant.jpg` | Every helmet worn on the head: compliant |
| `images/site-carried.jpg` | Helmets carried in the hand, not worn: the bottleneck case |
| `images/site-violation.jpg` | One worker without a helmet: an alert is raised |

Source: the [Safety Helmet Wearing Dataset](https://github.com/njvisionpower/Safety-Helmet-Wearing-Dataset),
MIT License. The detection boxes were drawn by that repository's model, not by Mayl; Mayl trains
no vision model. Full credit: [`images/CREDITS.md`](images/CREDITS.md).

These are the only non-synthetic data in Mayl. The datasets described in the project's
knowledge files (for example the 7,000 public and 1,200 client images in
`knowledge/ppe/ds/dataset-card.md`) belong to the fictional project and are not in this
repository. See [`docs/DATA.md`](../../../../docs/DATA.md).
