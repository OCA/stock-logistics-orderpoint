# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint Default Location",
    "summary": """
        This module allows to define a different default location than the stock location""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "depends": [
        "stock",
        "base_partition",
    ],
    "data": [
        "views/stock_warehouse.xml",
    ],
}
