# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockWarehouseOrderpoint(models.Model):

    _inherit = "stock.warehouse.orderpoint"

    def _compute_location_id(self):
        """Finds location id for changed warehouse."""
        no_default_orderpoints = set()
        for warehouse, orderpoints in self.partition("warehouse_id").items():
            # If warehouse is not set
            if not warehouse:
                for company, orderpoints_company in orderpoints.partition(
                    "company_id"
                ).items():
                    warehouse = self.env["stock.warehouse"].search(
                        [
                            ("company_id", "=", company.id),
                            ("default_orderpoint_location_id", "!=", False),
                        ],
                        limit=1,
                    )
                    default_location = warehouse.default_orderpoint_location_id
                    if default_location:
                        orderpoints_company.update({"location_id": default_location.id})
                    else:
                        no_default_orderpoints.update(orderpoints_company._ids)
            else:
                default_location = warehouse.default_orderpoint_location_id
                if default_location:
                    orderpoints.update({"location_id": default_location.id})
                else:
                    no_default_orderpoints.update(orderpoints._ids)
        return super(
            StockWarehouseOrderpoint, self.browse(no_default_orderpoints)
        )._compute_location_id()
