# Copyright 2026 ACSONE SA/NV (https://www.acsone.eu)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2.extras import execute_values

from odoo import api, fields, models


class StockLocationProductOrderpoint(models.Model):
    _name = "stock.location.product.orderpoint"
    _description = "Product Orderpoint"
    _check_company_auto = True

    stock_location_orderpoint_id = fields.Many2one(
        "stock.location.orderpoint",
        index=True,
        readonly=True,
    )
    trigger = fields.Selection(
        related="stock_location_orderpoint_id.trigger",
        readonly=True,
        store=True,
    )
    replenish_method = fields.Selection(
        related="stock_location_orderpoint_id.replenish_method",
        readonly=True,
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="stock_location_orderpoint_id.company_id",
        readonly=True,
        store=True,
    )
    location_src_id = fields.Many2one(
        "stock.location",
        related="stock_location_orderpoint_id.location_src_id",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        index=True,
        readonly=True,
    )
    qty_demand = fields.Float(
        "Demand",
        digits="Product Unit of Measure",
        readonly=True,
    )
    qty_available = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        help="Quantity avaialble at source location of "
        "the orderpoint at the time of the demand computation",
    )
    qty_procurement = fields.Float(
        "Qty to procure",
        digits="Product Unit of Measure",
    )
    horizon = fields.Date()

    @api.model
    def _get_snapshot_insert_columns(self):
        """Return ordered SQL columns used for snapshot bulk insert.

        Inherited modules can extend this list to insert extra stored columns.
        """
        return [
            "stock_location_orderpoint_id",
            "trigger",
            "replenish_method",
            "company_id",
            "product_id",
            "qty_demand",
            "qty_available",
            "qty_procurement",
            "horizon",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
        ]

    @api.model
    def _get_snapshot_row_values(
        self,
        orderpoint,
        product_id,
        demand_qty,
        available_qty,
        procurement_qty,
        horizon,
        uid,
        now,
        **kwargs,
    ):
        """Return a tuple of values for the given orderpoint and product to insert
        as a snapshot row.

        The values should be ordered based on the _get_snapshot_insert_columns method.

        Inherited modules can extend this method to provide values for extra stored columns.

        """
        return [
            orderpoint.id,
            orderpoint.trigger,
            orderpoint.replenish_method,
            orderpoint.company_id.id,
            product_id,
            demand_qty,
            available_qty,
            procurement_qty,
            horizon,
            uid,
            now,
            uid,
            now,
        ]

    @api.model
    def _build_snapshot_insert_rows(
        self,
        orderpoint,
        demand_data,
        available_qty_data,
        procurement_data,
        horizon,
        uid,
        now,
        **kwargs,
    ):
        """Build tuple rows for execute_values based on declared insert columns."""
        columns = self._get_snapshot_insert_columns()
        rows = []
        for product_id, demand_qty in demand_data.items():
            values = self._get_snapshot_row_values(
                orderpoint=orderpoint,
                product_id=product_id,
                demand_qty=demand_qty,
                available_qty=available_qty_data.get(product_id, 0),
                procurement_qty=procurement_data.get(product_id, 0),
                horizon=horizon,
                uid=uid,
                now=now,
                **kwargs,
            )
            rows.append(tuple(values))
        return columns, rows

    @api.model
    def _insert_snapshot_rows(self, columns, rows):
        """Insert rows in bulk using execute_values."""
        if not rows:
            return
        sql = f"""
            INSERT INTO {self._table} (
                {", ".join(columns)}
            ) VALUES %s
        """
        execute_values(self.env.cr, sql, rows, page_size=1000)
        self.invalidate_model()

    @api.model
    def _generate_orderpoint_product_demand(self, orderpoint_id):
        """
        Generate the demand and procurement quantity for the given orderpoint and its products.

        This methood removes all the existing stock.location.product.orderpoint records
        linked to the given orderpoint and creates new ones based on
        the products returned by the _get_candidate_products method of the orderpoint strategy.


        :param orderpoint_id: stock.location.orderpoint record id
        """
        orderpoint = self.env["stock.location.orderpoint"].browse(orderpoint_id)

        # We remove the existing records for the given orderpoint

        self.env.cr.execute(
            """
            DELETE FROM stock_location_product_orderpoint
                WHERE stock_location_orderpoint_id = %s
            """,
            (orderpoint_id,),
        )

        products = orderpoint._get_candidate_products(products=None)
        computer = orderpoint._get_replenishment_computer()
        demand_data = computer._compute_demand(products)
        qty_available_data = computer._compute_available_quantities(
            list(demand_data.keys())
        )
        procurement_data = computer._compute_procurement_qty(
            demand_data, qty_available_data=qty_available_data
        )

        columns, rows = self._build_snapshot_insert_rows(
            orderpoint=orderpoint,
            demand_data=demand_data,
            available_qty_data=qty_available_data,
            procurement_data=procurement_data,
            horizon=orderpoint._horizon_datetime,
            uid=self.env.uid,
            now=fields.Datetime.now(),
        )
        self._insert_snapshot_rows(columns, rows)

    def action_recompute_demand(self, orderpoint_id):
        """
        Action method to trigger the recomputation of the demand for the linked
        orderpoint of the record.
        """
        self._generate_orderpoint_product_demand(orderpoint_id)

    def action_replenish(self):
        """
        Action method to trigger the replenishment of the linked orderpoint for the
        product of the record.
        """
        lines_by_orderpoint = self.partition("stock_location_orderpoint_id")
        orderpoind_ids = [o.id for o in lines_by_orderpoint.keys()]
        orderpoints = (
            self.env["stock.location.orderpoint"].browse(orderpoind_ids).sorted()
        )
        for orderpoint in orderpoints:
            lines = lines_by_orderpoint[orderpoint]
            procurement_data = {
                line.product_id.id: line.qty_procurement for line in lines
            }
            procurements = orderpoint._build_procurements(procurement_data)
            result = orderpoint._execute_run_procurements(procurements)
            orderpoint._after_replenishment(result)
            lines.sudo().unlink()

    def action_open_quants(self):
        self.ensure_one()
        action = self.product_id.action_open_quants()
        domain = action["domain"] + [
            ("location_id", "child_of", self.location_src_id.id),
        ]
        action["domain"] = domain
        return action
