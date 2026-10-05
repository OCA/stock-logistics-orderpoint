# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class XyzClassificationProductLevel(models.Model):
    _name = "xyz.classification.product.level"
    _inherit = "mail.thread"
    _description = "XYZ Classification Product Level"
    _rec_name = "product_id"

    product_id = fields.Many2one(
        "product.product",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product template",
        index=True,
        readonly=True,
    )
    level_id = fields.Many2one(
        "xyz.classification.level",
        string="Classification level",
        required=True,
        tracking=True,
    )
    allowed_level_ids = fields.Many2many(
        "xyz.classification.level",
        compute="_compute_allowed_level_ids",
        help="Technical field holding the levels the product may be "
        "classified with, so that the form only offers those.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        related="level_id.company_id",
        store=True,
        index=True,
    )
    last_replenishment_date = fields.Date(
        string="Last replenishment run",
        readonly=True,
        help="Last day the procurement scheduler considered this product.",
    )
    next_replenishment_date = fields.Date(
        string="Next replenishment run",
        index=True,
        help="The procurement scheduler ignores this product until this date. "
        "It is set after every run from the interval of the level, and can be "
        "changed by hand to postpone a single product. An empty date means the "
        "product is due.",
    )
    days_to_next_replenishment = fields.Integer(
        string="Days until next run",
        compute="_compute_days_to_next_replenishment",
        help="Days left before the procurement scheduler considers this "
        "product again. Zero means it is due on the next run.",
    )

    _active_product_level_uniq = models.UniqueIndex(
        "(company_id, product_id) WHERE (active IS TRUE)",
        "A product can only have one XYZ classification level per company.",
    )

    @api.depends("product_id.company_id", "product_tmpl_id.company_id")
    def _compute_allowed_level_ids(self):
        Level = self.env["xyz.classification.level"]
        levels = Level.search(Domain("company_id", "in", self.env.companies.ids))
        by_company = levels.grouped("company_id")
        for rec in self:
            company = rec.product_id.company_id or rec.product_tmpl_id.company_id
            rec.allowed_level_ids = (
                by_company.get(company, Level) if company else levels
            )

    @api.depends("next_replenishment_date")
    def _compute_days_to_next_replenishment(self):
        today = fields.Date.context_today(self)
        for rec in self:
            due = rec.next_replenishment_date
            rec.days_to_next_replenishment = max((due - today).days, 0) if due else 0

    @api.constrains("product_id", "level_id")
    def _check_product_company(self):
        """A level may only classify a product of its own company.

        Spelled out rather than left to check_company, which reads company_id:
        a related field still holding the previous company when the level of an
        existing record is moved to another one."""
        for rec in self:
            product_company = rec.product_id.company_id
            if product_company and product_company != rec.level_id.company_id:
                raise ValidationError(
                    self.env._(
                        "The product %(product)s belongs to company "
                        "%(product_company)s, so it cannot be classified with "
                        "%(level)s, which belongs to %(level_company)s.",
                        product=rec.product_id.display_name,
                        product_company=product_company.display_name,
                        level=rec.level_id.name,
                        level_company=rec.level_id.company_id.display_name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Fill in the product and its template from whichever one is given.

        The product form is a window onto the single variant of its template,
        so its levels list only ever knows the template. Above one variant
        nothing is guessed: there is no telling which one is meant."""
        templates = self.env["product.template"].browse(
            {
                vals["product_tmpl_id"]
                for vals in vals_list
                if vals.get("product_tmpl_id") and not vals.get("product_id")
            }
        )
        variants = self.env["product.product"].browse(
            {
                vals["product_id"]
                for vals in vals_list
                if vals.get("product_id") and not vals.get("product_tmpl_id")
            }
        )
        variant_of = {
            template.id: template.product_variant_id.id
            for template in templates
            if template.product_variant_count == 1
        }
        template_of = {variant.id: variant.product_tmpl_id.id for variant in variants}
        for vals in vals_list:
            if not vals.get("product_id"):
                variant_id = variant_of.get(vals.get("product_tmpl_id"))
                if variant_id:
                    vals["product_id"] = variant_id
            elif not vals.get("product_tmpl_id"):
                template_id = template_of.get(vals["product_id"])
                if template_id:
                    vals["product_tmpl_id"] = template_id
        return super().create(vals_list)

    @api.model
    def _get_orderpoint_skip_domain(self, company_id=False):
        """Return the domain excluding the orderpoints of postponed products.

        A level only postpones the orderpoints of its own company, even when
        the scheduler runs for all of them at once. An empty date never
        postpones anything."""
        domain = Domain("level_id.active", "=", True) & Domain(
            "next_replenishment_date", ">", fields.Date.context_today(self)
        )
        if company_id:
            domain &= Domain("company_id", "=", company_id)
        skip = Domain.TRUE
        for company, levels in self.sudo().search(domain).grouped("company_id").items():
            skip &= Domain("product_id", "not in", levels.product_id.ids) | Domain(
                "company_id", "!=", company.id
            )
        return skip

    @api.model
    def _mark_replenishment_run_for_products(self, products, company_id=False):
        """Consume the replenishment window of the levels of these products.

        The window is consumed by the product having been *considered*, not by
        an order having been placed: that is what lets the demand of a slow
        mover pile up into one order instead of a handful of tiny ones.

        Archived levels are skipped here and in _get_orderpoint_skip_domain
        alike, or their products would be postponed by a run that never
        stamped them."""
        domain = Domain("level_id.active", "=", True) & Domain(
            "product_id", "in", products.ids
        )
        if company_id:
            domain &= Domain("company_id", "=", company_id)
        today = fields.Date.context_today(self)
        levels = self.sudo().search(domain)
        for level, records in levels.grouped("level_id").items():
            records.write(
                {
                    "last_replenishment_date": today,
                    "next_replenishment_date": today
                    + timedelta(days=level.replenishment_interval_days),
                }
            )
        return levels
