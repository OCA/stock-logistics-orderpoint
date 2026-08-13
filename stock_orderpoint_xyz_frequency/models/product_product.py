# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    xyz_classification_product_level_ids = fields.One2many(
        "xyz.classification.product.level", inverse_name="product_id"
    )
