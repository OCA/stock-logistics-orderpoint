Set default supplier on product "Replenish" wizard.

When an orderpoint exists, odoo doesn't set the default supplier in the
"Replenish" wizard if not set on the orderpoint. But it is not required to set
a supplier on an orderpoint (the field is even hidden by default), it will default
to the main product supplier.
