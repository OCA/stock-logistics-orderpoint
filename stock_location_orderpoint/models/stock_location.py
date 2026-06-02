# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models, tools
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval


def make_hashable(val):
    if isinstance(val, list):
        return tuple(make_hashable(v) for v in val)
    if isinstance(val, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in val.items()))
    return val


class StockLocation(models.Model):
    _inherit = "stock.location"

    location_orderpoint_ids = fields.One2many(
        comodel_name="stock.location.orderpoint",
        inverse_name="location_id",
        string="Location Orderpoints",
        help="Location Orderpoints. Rules that allows this location to be replenished.",
    )
    location_orderpoint_count = fields.Integer(
        compute="_compute_location_orderpoint_count",
    )

    def _compute_location_orderpoint_count(self):
        groups = self.env["stock.location.orderpoint"].read_group(
            [("location_id", "in", self.ids)], ["location_id"], ["location_id"]
        )
        result = {
            data["location_id"][0]: (data["location_id_count"]) for data in groups
        }
        for location in self:
            location.location_orderpoint_count = result.get(location.id, 0)

    def action_open_location_orderpoints(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock_location_orderpoint.action_stock_location_orderpoint"
        )
        action["domain"] = [("location_id", "in", self.ids)]
        if len(self.ids) == 1:
            if "context" in action:
                context = safe_eval(action["context"])
                context.update({"default_location_id": self.id})
                action["context"] = str(context)
            else:
                action["context"] = str({"default_location_id": self.id})
        return action

    @api.model
    @tools.ormcache_context("location_id", keys=("excluded_location_domain_cache_key",))
    def _get_cached_stock_domains(self, location_id):
        return self.env["product.product"]._get_domain_locations_new(location_id)

    def _get_stock_domains(self, location_id):
        domain = self.env.context.get("excluded_location_domain", [])
        return self.with_context(
            excluded_location_domain_cache_key=make_hashable(domain)
        )._get_cached_stock_domains(location_id)

    @api.model
    def _get_consuming_moves_domain(self, location_id):
        """Get the domain to apply on stock.move to get the consuming moves of a location."""
        (
            _q,
            _il,
            domain_move_out_loc,
        ) = self._get_stock_domains(location_id)
        domain = [
            ("state", "in", ("confirmed", "partially_available")),
        ]
        return expression.AND([domain_move_out_loc, domain])

    @api.model
    def _get_replenishing_moves_domain(self, location_id):
        """Get the domain to apply on stock.move to get the moves replenishing a location."""
        (
            _q,
            domain_move_in_loc,
            _ol,
        ) = self._get_stock_domains(location_id)
        domain = [
            ("state", "in", ("confirmed", "assigned", "partially_available")),
        ]
        return expression.AND([domain_move_in_loc, domain])

    @api.model
    def _get_replenished_moves_domain(self, location_id):
        """Get the domain to apply on stock.move to get the move having repeished the
        location."""
        (
            _q,
            domain_move_in_loc,
            _ol,
        ) = self._get_stock_domains(location_id)
        domain = [
            ("state", "=", "done"),
        ]
        return expression.AND([domain_move_in_loc, domain])

    def _clear_caches(self):
        self._get_cached_stock_domains.clear_cache(self)

    @api.model_create_multi
    def create(self, vals_list):
        self._clear_caches()
        return super().create(vals_list)

    def write(self, vals):
        self._clear_caches()
        return super().write(vals)

    def unlink(self):
        self._clear_caches()
        return super().unlink()
