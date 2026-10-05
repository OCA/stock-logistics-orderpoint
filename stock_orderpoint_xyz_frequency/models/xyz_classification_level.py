# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.fields import Domain


class XyzClassificationLevel(models.Model):
    _name = "xyz.classification.level"
    _description = "XYZ Classification Level"
    _order = "sequence, id"

    name = fields.Char(required=True, help="Classification X, Y or Z")
    sequence = fields.Integer(
        default=10,
        help="Levels are ordered from the steadiest demand to the most erratic one.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    replenishment_interval_days = fields.Integer(
        string="Replenishment interval (days)",
        required=True,
        default=1,
        help="Number of days the procurement scheduler waits before "
        "considering the products of this level again. 1 means every day, "
        "which is the standard behaviour. A larger value lets the demand of a "
        "slow mover pile up, so that it is replenished in one go.",
    )

    _name_uniq = models.Constraint(
        "UNIQUE(company_id, name)",
        "A classification level with that name already exists in this company.",
    )
    _replenishment_interval_days_positive = models.Constraint(
        "CHECK(replenishment_interval_days >= 1)",
        "The replenishment interval must be at least 1 day.",
    )

    def write(self, vals):
        """Archive the classifications along with the level, never the other
        way round: the product may have been classified elsewhere since, and
        unarchiving would give it two live classifications, which is refused."""
        res = super().write(vals)
        if "active" in vals and not vals["active"]:
            self.env["xyz.classification.product.level"].search(
                [("level_id", "in", self.ids)]
            ).write({"active": False})
        return res

    @api.onchange("name", "company_id")
    def _onchange_name(self):
        """Point at the archived twin instead of letting the save fail on it:
        the name is unique per company whether the level is archived or not."""
        if not self.name:
            return
        archived = self.with_context(active_test=False).search(
            Domain("name", "=", self.name)
            & Domain("company_id", "=", self.company_id.id)
            & Domain("active", "=", False)
            & Domain("id", "!=", self._origin.id),
            limit=1,
        )
        if archived:
            return {
                "warning": {
                    "title": self.env._("Archived level"),
                    "message": self.env._(
                        "The level %(name)s already exists in this company, "
                        "archived. Unarchive it rather than creating a second "
                        "one, which would be refused.",
                        name=archived.name,
                    ),
                }
            }

    def action_reset_replenishment_windows(self):
        """Make every product of these levels due on the next scheduler run: a
        shortened interval would otherwise wait for the old window to elapse."""
        self.env["xyz.classification.product.level"].search(
            [("level_id", "in", self.ids)]
        ).write({"next_replenishment_date": False})
        return True
