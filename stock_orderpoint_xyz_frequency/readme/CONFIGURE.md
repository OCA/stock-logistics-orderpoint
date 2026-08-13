1.  Go to Inventory / Configuration / Products / XYZ Classification
    Levels and create your levels, ordered from the steadiest demand to
    the most erratic one, each with its **Replenishment interval
    (days)**:

    | Sequence | Name | Interval |
    |----------|------|----------|
    | 1        | X    | 1        |
    | 2        | Y    | 7        |
    | 3        | Z    | 30       |

    An interval of 1 is the standard Odoo behaviour. Levels belong to a
    company, so create them in each company you manage; a product shared
    between two companies can sit at a different level in each.

2.  Classify your slow movers, either from the XYZ Classification tab of
    the product form or from Inventory / Products / Products XYZ
    Classification, where the whole classification is edited as one list.

3.  Check that those products have a **reordering rule** with a minimum,
    a maximum and the trigger set to **Auto**. That rule is what the
    scheduler replenishes, so a classified product without one is never
    looked at and its dates stay empty.
