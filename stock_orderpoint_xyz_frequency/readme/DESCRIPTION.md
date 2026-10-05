The procurement scheduler runs once a day and looks at every automatic
reordering rule. For a slow mover whose minimum and maximum quantities are
small, that produces a stream of tiny replenishment orders — one or two
units at a time — with no chance to consolidate them.

This module classifies products the way an XYZ analysis does — by how
*predictable* their demand is, where X products sell steadily, Y products
fluctuate and Z products move erratically or rarely — and gives every
level a **replenishment interval in days**. The scheduler then ignores a
product until that many days have gone by since it was last considered.
The demand accumulates in the meantime, so when the product comes up again
it is replenished in one larger order: enough for a bulk discount, a full
pallet, or simply one receipt instead of five.

The daily scheduler keeps running exactly as before. It just looks at
fewer products on any given day, and only ever the ones you classified: a
product with no level is replenished as it always was.
