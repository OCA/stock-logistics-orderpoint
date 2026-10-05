There is nothing to run. The next time the *Replenishment* scheduled
action runs, a classified product whose window has not elapsed is left
alone. A product with no level is replenished as before.

Take a Z product with a reordering rule of min 2 / max 4 and a 30-day
interval:

| Day | Event                              | Scheduler  |
|-----|------------------------------------|------------|
| 1   | stock is 4, nothing to order       | considered |
| 5   | 3 sold, forecast 1                 | skipped    |
| 12  | 3 sold, forecast -2                | skipped    |
| 25  | 4 sold, forecast -6                | skipped    |
| 31  | orders 4 - (-6) = 10 units         | considered |

One order of 10 instead of four small ones. The window is consumed by
the product having been **considered** on day 1, not by an order having
been placed.

Three columns tell you where a product stands:

- **Last replenishment run**: the day the scheduler last considered it.
- **Next replenishment run**: the day it is due again. Editable, to
  postpone a single product or to spread a level over the month instead
  of replenishing all of it on the same day.
- **Days until next run**: the same thing counted from today, zero when
  the product is due. It is computed rather than stored, so it can be
  neither sorted nor searched on; use the **Postponed** and **Due**
  filters instead.

Empty dates mean the scheduler has never considered the product, nine
times out of ten because it has no automatic reordering rule.

Worth knowing:

- A human is never blocked. The **Order Once** button of the
  Replenishment report orders immediately, whatever the window says.
- A stockout does not reopen the window: a Z product that goes negative
  on day 5 waits until day 31. Give it a shorter interval or a larger
  maximum quantity if that is not what you want.
- Changing the interval of a level only takes effect once its products
  have been considered again. Use the **Reset windows** button on the
  level to make them all due immediately.
- The cadence is per product and per company, not per warehouse: all the
  reordering rules a company has for a product share one window.
- Archiving a level archives the classifications using it, and its
  products go back to being considered on every run. Archived records
  are out of the lists; the **Archived** filter brings them back, greyed
  out.
- Restoring takes two steps: unarchive the level, then the products you
  want back. A product carries one live classification per company, so
  anything reclassified in the meantime keeps its new level.
- An archived level keeps its name reserved, and you are warned if you
  type it again: unarchive the old one rather than create a second.
