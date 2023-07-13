# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Location Orderpoint Average Daily Sale",
    "summary": """
        This module allows to base replenishments quantities (on stock locations)
        on average daily sales""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "ACSONE SA/NV, BCIM, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "depends": [
        "stock_location_orderpoint",
        "stock_average_daily_sale",
    ],
}
