# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import mute_logger

from .common import XYZClassificationCase


class TestXYZClassification(XYZClassificationCase):
    def test_a_level_name_is_unique_within_its_company(self):
        """The same name in another company is free, which is what setUpClass
        relies on to create level_bis_a."""
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            self.Level.create({"name": "a"})

    def test_a_level_only_shows_in_its_own_company(self):
        levels = self.Level.with_user(self.user_bis).search([("name", "=", "a")])
        self.assertEqual(levels, self.level_bis_a)

    def test_a_product_has_a_single_level_per_company(self):
        self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_a.id}
        )
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            self.ProductLevel.create(
                {"product_id": self.product_product.id, "level_id": self.level_b.id}
            )

    def test_the_same_product_is_classified_again_in_another_company(self):
        levels = self.ProductLevel.create(
            [
                {"product_id": self.product_product.id, "level_id": self.level_a.id},
                {
                    "product_id": self.product_product.id,
                    "level_id": self.level_bis_a.id,
                },
            ]
        )
        self.assertEqual(
            levels.mapped("company_id"), self.env.company + self.company_bis
        )

    def test_a_product_owned_by_a_company_only_takes_its_levels(self):
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.ProductLevel.create(
                {"product_id": self.product_in_bis.id, "level_id": self.level_a.id}
            )
        product_level = self.ProductLevel.create(
            {"product_id": self.product_in_bis.id, "level_id": self.level_bis_a.id}
        )
        self.assertEqual(product_level.company_id, self.company_bis)

    def test_moving_a_level_to_another_company_is_refused(self):
        product_level = self.ProductLevel.create(
            {"product_id": self.product_in_bis.id, "level_id": self.level_bis_a.id}
        )
        with self.assertRaises(UserError):
            product_level.level_id = self.level_a

    def test_a_product_level_only_shows_in_its_own_company(self):
        self.ProductLevel.create(
            [
                {"product_id": self.product_product.id, "level_id": self.level_a.id},
                {
                    "product_id": self.product_product.id,
                    "level_id": self.level_bis_a.id,
                },
            ]
        )
        visible = self.ProductLevel.with_user(self.user_bis).search(
            [("product_id", "=", self.product_product.id)]
        )
        self.assertEqual(visible.company_id, self.company_bis)

    def test_the_levels_on_offer_follow_the_company_of_the_product(self):
        shared = self.ProductLevel.new({"product_id": self.product_product.id})
        self.assertEqual(self._offered_levels(shared), self.own_levels)
        owned = self.ProductLevel.new({"product_id": self.product_in_bis.id})
        self.assertEqual(self._offered_levels(owned), self.level_bis_a)
        alone = self.ProductLevel.with_context(
            allowed_company_ids=self.env.company.ids
        ).new({"product_id": self.product_product.id})
        self.assertEqual(self._offered_levels(alone), self.level_a + self.level_b)

    def test_an_archived_level_is_no_longer_offered(self):
        """The products already classified with it keep their level."""
        product_level = self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_a.id}
        )
        self.level_a.active = False
        offered = self.ProductLevel.new({"product_id": self.product_product.id})
        self.assertEqual(self._offered_levels(offered), self.level_b + self.level_bis_a)
        self.assertEqual(product_level.level_id, self.level_a)

    def test_creating_the_twin_of_an_archived_level_warns(self):
        """The name stays taken while archived, so the save would fail with
        nothing on screen to explain it."""
        self.level_a.active = False
        new_level = self.Level.new({"name": "a", "company_id": self.env.company.id})
        self.assertIn("archived", new_level._onchange_name()["warning"]["message"])
        free_name = self.Level.new({"name": "z", "company_id": self.env.company.id})
        self.assertFalse(free_name._onchange_name())

    def test_archiving_a_level_archives_its_classifications(self):
        """The other levels are left alone, and unarchiving brings nothing
        back: the product may have been classified elsewhere since."""
        other_product = self.env["product.product"].create(
            {"name": "Test other", "company_id": False}
        )
        on_a, on_b = self.ProductLevel.create(
            [
                {"product_id": self.product_product.id, "level_id": self.level_a.id},
                {"product_id": other_product.id, "level_id": self.level_b.id},
            ]
        )
        self.level_a.active = False
        self.assertFalse(on_a.active)
        self.assertTrue(on_b.active)
        self.level_a.active = True
        self.assertFalse(on_a.active)

    def test_an_archived_classification_frees_the_product(self):
        """Only the live classifications are unique, so the product is
        classified again while its history is kept out of sight."""
        archived = self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_a.id}
        )
        self.level_a.active = False
        reclassified = self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_b.id}
        )
        self.product_product.invalidate_recordset()
        self.assertEqual(
            self.product_product.xyz_classification_product_level_ids, reclassified
        )
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            archived.active = True
            archived.flush_recordset()

    def test_saving_the_product_form_keeps_the_archived_classifications(self):
        """The form hands the whole list back to the variant on save, and the
        archived lines are not part of it: they must survive it."""
        archived = self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_a.id}
        )
        self.level_a.active = False
        self.product_template.write(
            {
                "xyz_classification_product_level_ids": [
                    Command.create({"level_id": self.level_b.id})
                ]
            }
        )
        live = self.product_template.xyz_classification_product_level_ids
        self.product_template.write(
            {"xyz_classification_product_level_ids": [Command.set(live.ids)]}
        )
        self.assertTrue(archived.exists())
        self.assertFalse(archived.active)

    def test_a_new_line_of_the_template_list_is_offered_the_right_levels(self):
        """The list of the product form fills in the template, not the variant,
        so the offer has to be derived from it as well."""
        self.product_template.company_id = self.company_bis
        product_level = self.ProductLevel.new(
            {"product_tmpl_id": self.product_template.id}
        )
        self.assertEqual(product_level.allowed_level_ids._origin, self.level_bis_a)

    def test_the_product_and_its_template_fill_each_other_in(self):
        """The template list only ever sends the template, the variant form
        only ever sends the variant."""
        self.product_template.write(
            {
                "xyz_classification_product_level_ids": [
                    Command.create({"level_id": self.level_a.id})
                ]
            }
        )
        from_template = self.product_template.xyz_classification_product_level_ids
        self.assertEqual(from_template.product_id, self.product_product)
        from_variant = self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_bis_a.id}
        )
        self.assertEqual(from_variant.product_tmpl_id, self.product_template)

    def test_a_multi_variant_template_guesses_no_variant(self):
        """There is no telling which variant the level would be meant for."""
        self._create_variant(self.size_attr_value_m)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.ProductLevel.create(
                {
                    "product_tmpl_id": self.product_template.id,
                    "level_id": self.level_a.id,
                }
            )

    def test_a_level_of_the_variant_shows_on_its_template(self):
        product_level = self.ProductLevel.create(
            {"product_id": self.product_product.id, "level_id": self.level_a.id}
        )
        self.assertEqual(
            self.product_product.xyz_classification_product_level_ids, product_level
        )
        self.assertEqual(
            self.product_template.xyz_classification_product_level_ids, product_level
        )
        product_level.unlink()
        self.assertFalse(self.product_product.xyz_classification_product_level_ids)
        self.assertFalse(self.product_template.xyz_classification_product_level_ids)

    def test_a_multi_variant_template_shows_no_level(self):
        new_variant = self._create_variant(self.size_attr_value_m)
        product_level = self.ProductLevel.create(
            {"product_id": new_variant.id, "level_id": self.level_a.id}
        )
        self.assertEqual(
            new_variant.xyz_classification_product_level_ids, product_level
        )
        self.assertFalse(self.product_template.xyz_classification_product_level_ids)

    def test_a_level_linked_to_the_template_moves_to_its_variant(self):
        other_product = self.env["product.product"].create(
            {"name": "Test other", "company_id": False}
        )
        product_level = self.ProductLevel.create(
            {"product_id": other_product.id, "level_id": self.level_a.id}
        )
        self.product_template.write(
            {"xyz_classification_product_level_ids": [Command.link(product_level.id)]}
        )
        self.assertEqual(product_level.product_id, self.product_product)
        self.assertEqual(
            self.product_product.xyz_classification_product_level_ids, product_level
        )
