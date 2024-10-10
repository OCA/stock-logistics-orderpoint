Location orderpoints module was designed (first) to generate replenishment moves 
for particular stock locations. e.g.: we have a reserve stock and a preparation
stock.

As warehouse life is not static, moves for a product can be canceled, preparation
stock could have been refilled with another move, ...

So, generated moves from location orderpoints can become obsolete.

This module should help to clean orderpoint moves and regenerate moves.
