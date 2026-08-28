# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockOrderpointStrength(models.Model):
    _name = "stock.orderpoint.strength"
    _description = "Stock Orderpoint Strength"

    active = fields.Boolean(default=True)
    strength = fields.Float(
        required=True,
        default=1.0,
        help="Weight of this location's claim on contended stock, relative to "
        "the locations it competes with: 0.5 against 1 shares the stock the "
        "same way 1 against 2 does. Values below 1 are allowed and weaken the "
        "claim. Has no effect when supply is enough for every competing "
        "orderpoint to reach its target.",
    )
    date_start = fields.Date(required=True, string="From")
    date_stop = fields.Date(required=True, string="To")
    location_id = fields.Many2one(comodel_name="stock.location", required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )

    # In the database rather than in a constrains, because the weighting
    # divides by the sum of the weights in play: a zero that slipped in past
    # the ORM would break the split itself, not just the record.
    _strength_positive = models.Constraint(
        "CHECK(strength > 0)",
        "Strength must be greater than 0.",
    )

    @api.depends("location_id")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.location_id.display_name}"

    @api.constrains("date_start", "date_stop")
    def _check_date_window(self):
        for record in self:
            if record.date_stop < record.date_start:
                raise ValidationError(
                    self.env._("The end date must not precede the start date.")
                )

    @api.model
    def _get_effective_strength(self, location, run_date, lead_days=0.0):
        """The weight of this location's claim, on the day the goods are needed.

        A location with no record in force weighs 1, so locations nobody has
        configured still compete with each other, on equal terms.
        """
        reference_date = run_date + timedelta(days=lead_days)
        records = self.search(
            [
                ("location_id", "=", location.id),
                ("company_id", "in", [False, location.company_id.id]),
                ("date_start", "<=", reference_date),
                ("date_stop", ">=", reference_date),
            ]
        )
        effective = 1.0
        for record in records:
            effective *= record.strength
        return effective
