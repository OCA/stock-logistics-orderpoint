# Copyright 2026 Camptocamp SA (https://www.camptocamp.com).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Stock Orderpoint Safety Stock",
    "summary": "Automatically compute the safety stock for orderpoints",
    "version": "19.0.1.0.1",
    "author": "Camptocamp, Odoo Community Association (OCA)",
    "maintainers": ["ivantodorovich"],
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
    "license": "AGPL-3",
    "category": "Inventory",
    "depends": ["stock"],
    "external_dependencies": {
        "python": ["pyerf"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/stock_cycle_service_level.xml",
        "views/stock_cycle_service_level.xml",
        "views/stock_warehouse_orderpoint.xml",
        "wizards/res_config_settings.xml",
        "wizards/stock_replenishment_info.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_orderpoint_safety_stock/static/src/**/*.js",
            "stock_orderpoint_safety_stock/static/src/**/*.xml",
        ],
    },
}
