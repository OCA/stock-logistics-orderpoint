# Copyright 2025 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint Source Available",
    "summary": """This module will allow to create movements from orderpoints
    only if product is available at location source""",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "maintainers": ["rousseldenis"],
    "author": "ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "depends": [
        "stock",
        "stock_orderpoint_source_from_route",
    ],
    "data": ["views/stock_route.xml", "views/stock_warehouse_orderpoint.xml"],
}
