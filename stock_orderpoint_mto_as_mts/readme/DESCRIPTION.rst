This module aims to materialize the triggering of another stock rule through
an orderpoint in the procurement of MTO products.

The MTO route will loose it's MTO rule as this is replaced by the generated orderpoints.
When a product is configured as MTO, then an orderpoint with min/max of zero is created.
When the product is not anymore configured as MTO, the orderpoint can be automatically archived depending on the configuration you choose on the warehouse.
