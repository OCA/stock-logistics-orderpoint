# Copyright 2023 Michael Tietz (MT Software) <mtietz@mt-software.de>
# Copyright 2026 ACSONE SA/NV (https://acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "stock_location_orderpoint",
    "author": "MT Software, BCIM, ACSONE SA/NV, Odoo Community Association (OCA)",
    "summary": "Declare orderpoint on a location "
    "allowing to replenish any product with the same criteria.",
    "version": "16.0.3.0.0",
    "data": [
        "security/ir.model.access.csv",
        "security/stock_location_orderpoint_security.xml",
        "data/ir_cron.xml",
        "data/ir_sequence.xml",
        "data/queue_job_channel.xml",
        "data/queue_job_function.xml",
        "views/stock_location_orderpoint_views.xml",
        "views/stock_location.xml",
        "views/menu.xml",
    ],
    "demo": [
        "demo/stock_location.xml",
        "demo/stock_picking_type.xml",
        "demo/stock_route.xml",
        "demo/stock_location_orderpoint.xml",
    ],
    "depends": [
        "stock_available_base_exclude_location",
        "stock_helper",
        "queue_job",
    ],
    "license": "AGPL-3",
    "maintainers": ["mt-software-de", "lmignon"],
    "website": "https://github.com/OCA/stock-logistics-orderpoint",
}
