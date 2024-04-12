# Copyright 2024 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Stock Orderpoint Default Warehouse Location",
    "summary": "Allow to configure on the warehouse the orderpoint location",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "BCIM, Camptocamp, Odoo Community Association (OCA)",
    "maintainers": ["jbaudoux"],
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "depends": [
        "stock_location_orderpoint",
    ],
    "data": [
        "views/stock_warehouse_view.xml",
    ],
    "installable": True,
}
