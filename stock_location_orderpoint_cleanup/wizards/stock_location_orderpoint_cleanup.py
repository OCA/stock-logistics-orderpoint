# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.fields import Command


class StockLocationOrderpointCleanup(models.TransientModel):

    _name = "stock.location.orderpoint.cleanup"
    _description = "Wizard to cleanup the generated moves through location orderpoints"

    orderpoint_ids = fields.Many2many(
        comodel_name="stock.location.orderpoint",
        name="Orderpoints",
        ondelete="cascade",
    )
    run_after = fields.Boolean(
        help="Check this if you want to run the orderpoint after cleanup."
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list=fields_list)
        if "orderpoint_id" not in res:
            if self.env.context.get(
                "active_model"
            ) == "stock.location.orderpoint" and self.env.context.get("active_ids"):
                active_ids = self.env.context.get("active_ids")
                res["orderpoint_ids"] = [Command.set(active_ids)]

        return res

    def doit(self):
        for wizard in self:
            wizard.orderpoint_ids.cleanup(run_after=wizard.run_after)
        return {"type": "ir.actions.act_window_close"}
