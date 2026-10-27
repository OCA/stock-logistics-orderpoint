# Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestStrengthResolution(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.strength_model = cls.env["stock.orderpoint.strength"]
        cls.location = cls.env["stock.location"].create(
            {"name": "Test Spoke", "usage": "internal"}
        )

    def _create(self, strength, date_start, date_stop, **values):
        return self.strength_model.create(
            {
                "location_id": self.location.id,
                "strength": strength,
                "date_start": date_start,
                "date_stop": date_stop,
                **values,
            }
        )

    def test_no_record_defaults_to_one(self):
        """The weight a location has before anyone configures anything."""
        effective = self.strength_model._get_effective_strength(
            self.location, date(2026, 7, 20)
        )
        self.assertEqual(effective, 1.0)

    def test_multiplicative_stacking(self):
        self._create(2.0, date(2026, 6, 1), date(2026, 8, 31))
        self._create(0.5, date(2026, 7, 20), date(2026, 7, 20))
        effective = self.strength_model._get_effective_strength(
            self.location, date(2026, 7, 20)
        )
        self.assertEqual(effective, 1.0)

    def test_window_offset_by_lead_time(self):
        """The window is read on the day the goods are needed, not ordered."""
        self._create(3.0, date(2026, 7, 20), date(2026, 7, 20))
        active_run = self.strength_model._get_effective_strength(
            self.location, date(2026, 7, 17), lead_days=3
        )
        inactive_run = self.strength_model._get_effective_strength(
            self.location, date(2026, 7, 20), lead_days=3
        )
        self.assertEqual(active_run, 3.0)
        self.assertEqual(inactive_run, 1.0)

    def test_another_companys_record_is_ignored(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        self._create(
            3.0, date(2026, 1, 1), date(2026, 12, 31), company_id=other_company.id
        )
        effective = self.strength_model._get_effective_strength(
            self.location, date(2026, 7, 20)
        )
        self.assertEqual(effective, 1.0)

    def test_display_name(self):
        record = self._create(2.0, date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(record.display_name, "Test Spoke")

    def test_a_weight_below_one_is_allowed(self):
        """Only the ratio between competing weights matters, not the scale."""
        self._create(0.25, date(2026, 1, 1), date(2026, 12, 31))
        effective = self.strength_model._get_effective_strength(
            self.location, date(2026, 7, 20)
        )
        self.assertEqual(effective, 0.25)

    @mute_logger("odoo.sql_db")
    def test_strength_must_be_positive(self):
        """Enforced by the database: the split divides by the weights in play."""
        for rejected in (0, -1, -0.5):
            with self.assertRaises(IntegrityError), self.cr.savepoint():
                self._create(rejected, date(2026, 1, 1), date(2026, 12, 31))
                self.env.flush_all()

    def test_date_window_constraint(self):
        with self.assertRaises(ValidationError):
            self._create(1.0, date(2026, 12, 31), date(2026, 1, 1))
