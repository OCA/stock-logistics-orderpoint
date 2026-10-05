# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint Strength",
    "summary": "Weight orderpoint replenishment claims when source stock is contended",
    "version": "19.0.1.0.0",
    "development_status": "Alpha",
    "category": "Inventory",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "author": "Ariel Barreiros, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_orderpoint_strength_views.xml",
    ],
    "installable": True,
}
