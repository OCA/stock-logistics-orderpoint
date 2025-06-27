# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
{
    "name": "Stock Orderpoint Mto As Mts",
    "summary": "Materialize need from MTO route through orderpoint",
    "version": "18.0.1.1.0",
    "development_status": "Alpha",
    "category": "Operations/Inventory/Delivery",
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "author": "BCIM, Camptocamp, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "base_partition",
        "product_route_mto",
        "stock",
        "stock_orderpoint_default_location",
    ],
    "data": [
        "views/stock_warehouse_views.xml",
    ],
}
