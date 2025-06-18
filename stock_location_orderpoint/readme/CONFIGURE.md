## First configuration

1.  In order to replenish your stock location from another one, you
    first need to set the multi locations configuration.
2.  So, go to Inventory \> Configuration \> Settings \> Warehouse
3.  Check the 'Storage Locations' box.
4.  As you should be able to configure a dedicated route to
    replenishment, you should also activate, in the same menu, the
    'Multi-Step Routes' box.

## Locations configuration

1.  Identify the location you want to apply a replenishment rule (e.g.:
    WH/Stock)
2.  Create (if not exists) a new location for replenishment under
    Warehouse view (e.g.: WH) location as we want to get the stock in
    replenishment taken into account of our product stock total
    quantity.

## Route Configuration

1.  You should configure at least a route with a rule that:

    > - Pull from the Replenishment stock location.
    > - For the stock location you want to (e.g.: WH/Stock)

## Location Orderpoint configuration

1.  Go either by the stock location you want to replenish and click on
    'Orderpoints' or go to Inventory \> Configuration \> Warehouse \>
    Stock Location Orderpoint

2.  Click on 'Create'

3.  Set a sequence

4.  Choose if the rule will be applied:

    > - Automatically (Auto/realtime): at each stock movement on the
    >   stock location, the rule will be evaluated.
    > - Manually (Manual): If set, an action 'Run Replenishment' will be
    >   displayed on the rule and allow to run it manually.
    > - by cron (Scheduled): A cron job will trigger the replenishment
    >   rules of this kind.

5.  Choose a replenish method:

    > - Fill up: The replenishment will be triggered when a move is
    >   waiting availability and forecast quantity is negative at the
    >   location (i.e. min=0). The replenished quantity will bring back
    >   the forecast quantity to 0 (i.e. max=0) but will be limited to
    >   what is available at the source location to plan only reservable
    >   replenishment moves.

6.  Choose the location to replenish

7.  Choose the route to use to replenish. The source location will be
    computed automatically based on the route value.

8.  Define a procurement group if you want to group some movements
    together.

9.  Define a priority for the created moves.

10. If you want to filter the stock locations that should be taken in
    consideration for product available quantities when triggering a
    replenishment (e.g.: Supplier locations - to avoid confirmed
    receptions taken into account), fill in the 'Domain to filter
    locations' field.
