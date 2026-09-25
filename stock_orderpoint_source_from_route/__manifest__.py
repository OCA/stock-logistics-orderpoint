# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint Source From Route",
    "summary": """This module allows to display the source location computed
    from the filled in route""",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV,Odoo Community Association (OCA)",
    "maintainers": ["rousseldenis"],
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "depends": ["stock", "stock_route_location_source"],
    "data": [
        "views/stock_warehouse_orderpoint.xml",
    ],
}
