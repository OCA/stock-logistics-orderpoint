When several locations are replenished from the same stock and there is not enough for all of them, Odoo reserves as first come - first served: the transfer that reaches the queue first takes everything it needs, and the ones behind it get nothing.

This module gives a location a **strength** for a date range. When stock runs short, the competing transfers reserve in proportion to their strength instead of by order of arrival.

## Example

The hub has 6 units on hand. Warehouse A and Warehouse B each ask for 10.

| Reserved                      | Warehouse A | Warehouse B |
| ----------------------------- | ----------- | ----------- |
| Odoo standard behaviour       | 6           | 0           |
| This module, no strengths     | 3           | 3           |
| Warehouse B set to strength 2 | 2           | 4           |

In all three cases both transfers still ask for 10.

## What changes

Two of these happen on their own, with nothing configured. Read them before installing.

- **Installing the module is enough to change replenishment.** A location with no record has a strength of 1, so contended stock is split evenly from the moment it is installed. Strength records only change the proportions.
- **A replenishment transfer's reservation is provisional until it is picked.** Take the same 6 units, but Warehouse A's transfer is created on a day when nothing else competes: it reserves all 6. When Warehouse B starts competing the next day, Warehouse A hands 3 back and drops to 3, without anyone touching its transfer. Ticking **Picked**, or validating the transfer, settles its reservation for good. Without this the split would only ever be right when every competing transfer happened to be created on the same day.
- **Only reordering rules with "Auto trigger take part.** A transfer created by hand is never rearranged, picked or not, and the stock it holds is not shared out to anyone else.
