Go to **Inventory > Configuration > Warehouse Management > Orderpoint Strengths** and create a record:

- **Location** -- the location being replenished, the one a reordering rule fills.
- **Strength** -- how heavily this location's claim counts. It is relative, so 0.5 against 1 splits the stock exactly like 1 against 2. It must be greater than 0.
- **From** / **To** -- the dates the strength applies.

Locations with no record have a strength of 1. To favour one shop for a season, that is the only record you need.

Nothing needs configuring on the reordering rules themselves, beyond their trigger being **Auto**. Rules set to Manual are left out of the weighting entirely.

Two records on the same location and overlapping dates multiply: 2 and 1.5 in force on the same day give a strength of 3. The dates are read on the day the goods are needed rather than the day the scheduler runs, so the reordering rule's lead time is taken into account.

Archive a record to stop it counting without losing it.
