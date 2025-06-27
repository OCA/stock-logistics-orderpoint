# Copyright 2023 ACSONE SA/NV
# Copyright 2025 Jacques-Etienne Baudoux (BCIM) <je@bcim.be>
# Copyright 2025 Michael Tietz (MT Software) <mtietz@mt-software.de>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, models
from odoo.tools import split_every

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _prepare_orderpoint_vals_base(self):
        return {
            "active": True,
            "product_min_qty": 0,
            "product_max_qty": 0,
            "trigger": "auto",
        }

    def _prepare_missing_orderpoint_vals(self, warehouse):
        vals = self._prepare_orderpoint_vals_base()
        vals.update(
            {
                "name": "MTO",  # give a name as next_by_code is too slow for large data
                "warehouse_id": warehouse.id,
                "product_id": self.id,
                "company_id": warehouse.company_id.id,
            }
        )
        return vals

    def _ensure_default_orderpoint_for_mto(self):
        """Ensure that a default orderpoint is created for the MTO products.

        Perform this on all product companies.
        """
        if not self:
            return
        _logger.debug("Ensure orderpoint for MTO")
        products_by_company = self._read_group(
            domain=[
                ("id", "in", self.ids),
                ("is_mto", "=", True),
                ("purchase_ok", "=", True),
            ],
            groupby=["company_id"],
            aggregates=["id:recordset"],
        )
        if not products_by_company:
            return
        wh_obj = self.env["stock.warehouse"]
        op_obj = self.env["stock.warehouse.orderpoint"]
        orderpoint_vals_base = self._prepare_orderpoint_vals_base()
        all_mto_wh = wh_obj.search([("mto_as_mts", "=", True)])
        all_mto_wh_by_company = all_mto_wh.grouped("company_id")
        op_vals_list = []
        for company, products in products_by_company:
            if company:
                mto_wh = all_mto_wh_by_company.get(company)
            else:
                mto_wh = all_mto_wh
            if not mto_wh:
                continue
            locations = self.env["stock.location"].browse()
            for wh in mto_wh:
                locations |= wh._get_locations_for_mto_orderpoints()
            # Reactivate inactive orderpoints
            inactive_ops = op_obj.with_context(active_test=False).search(
                [
                    ("active", "=", False),
                    ("location_id", "in", locations.ids),
                    ("product_id", "in", products.ids),
                ]
            )
            if inactive_ops:
                inactive_ops.write(orderpoint_vals_base)
            # Find products having an orderpoint for that wh
            products_by_wh = dict(
                op_obj._read_group(
                    domain=[
                        ("product_id", "in", products.ids),
                        ("warehouse_id", "in", mto_wh.ids),
                    ],
                    groupby=["warehouse_id"],
                    aggregates=["product_id:recordset"],
                )
            )
            # Prepare missing orderpoints
            for warehouse in mto_wh:
                _logger.debug(f"Prepare orderpoint for warehouse {warehouse.name}")
                missing_products = products - products_by_wh.get(
                    warehouse, products.browse()
                )
                for product in missing_products:
                    op_vals_list.append(
                        product._prepare_missing_orderpoint_vals(warehouse)
                    )
        chunk_size = models.INSERT_BATCH_SIZE * 20
        _logger.debug(
            f"Create orderpoint for MTO: {len(op_vals_list)} to create - "
            f"{len(op_vals_list)//chunk_size+1} chunks"
        )
        for i, op_vals_list_chunk in enumerate(split_every(chunk_size, op_vals_list)):
            _logger.debug(f"Create orderpoint for MTO - chunk {i}")
            ops = op_obj.create(op_vals_list_chunk)
            # free memory usage
            ops.invalidate_model()

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        products._ensure_default_orderpoint_for_mto()
        return products

    def _get_orderpoints_to_archive_domain(self, warehouses):
        domain = []
        locations = self.env["stock.location"]
        for warehouse in warehouses:
            locations |= warehouse._get_locations_for_mto_orderpoints()
        domain.extend(
            [
                ("product_id", "in", self.ids),
                ("product_min_qty", "=", 0.0),
                ("product_max_qty", "=", 0.0),
                ("location_id", "in", locations.ids),
                ("trigger", "=", "auto"),
            ]
        )
        return domain

    def _archive_orderpoints_on_mto_removal(self, forceall=False):
        if not self:
            return
        warehouses = self.env["stock.warehouse"].search(
            [
                ("mto_as_mts", "=", True),
                ("archive_orderpoints_mto_removal", "=", True),
            ]
        )
        if not warehouses:
            return
        if not forceall:
            self = self.filtered(lambda p: not p.is_mto)
        if not self:
            return
        domain = self._get_orderpoints_to_archive_domain(warehouses)
        if not domain:
            return
        ops = self.env["stock.warehouse.orderpoint"].search(domain)
        if ops:
            ops.write({"active": False})
