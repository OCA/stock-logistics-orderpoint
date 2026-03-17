## General Settings > Inventory

- **Demand History Days**: Define the rolling window for the historical analysis to compute the average daily demand and resulting safety stock. Default: 365. Company-specific.

## Orderpoint (per replenishment rule)

**Safety Stock Method**

- **Manual**: The product's min and max quantities are set manually (standard Odoo behavior).
- **Cycle Service Level**: The product's min and max quantities are computed based on the target cycle service level, growth factor, order cycle and lead times.

**Cycle Service Level**

Defines the target probability of meeting all demand during a replenishment cycle without running out of stock. Typical values range from 90% to 99%.

A higher target increases safety stock to reduce the risk of stockouts; a lower target reduces inventory at the cost of more frequent shortages.

**Cycle Days**

The desired number of days between orders.
Used to size the gap between the min and max quantities, to cover the expected demand during the desired reordering cycle.

**Growth Factor**

An optional multiplier to account for expected growth in demand.
Will be applied to the safety stock and the resulting min and max quantities.
