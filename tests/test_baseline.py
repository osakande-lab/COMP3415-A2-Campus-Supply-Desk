"""Behavior to preserve when reorganizing the service and menu."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

from supplydesk.menu import run_menu
from supplydesk.service import OrderService


class BaselineTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_quote_and_placement_agree(self):
        items = [{"product_id": "hoodie", "quantity": 2}]
        quote = self.service.quote("student", items, "delivery")
        self.assertEqual(
            [quote[key] for key in ("subtotal_cents", "discount_cents", "delivery_cents", "total_cents")],
            [8000, 800, 600, 7800],
        )
        self.assertFalse(self.path.exists())
        order = self.service.place_order("student", items, "delivery")
        self.assertEqual({key: order[key] for key in quote}, quote)
        self.assertEqual(self.stock("hoodie"), 3)

    def test_standard_delivery_is_free_at_threshold(self):
        for quantity, fee, total in [(19, 600, 10100), (20, 0, 10000)]:
            with self.subTest(quantity=quantity):
                quote = self.service.quote(
                    "regular", [{"product_id": "notebook", "quantity": quantity}], "delivery"
                )
                self.assertEqual(quote["delivery_cents"], fee)
                self.assertEqual(quote["total_cents"], total)

    def test_invalid_placement_leaves_saved_state_and_next_id_unchanged(self):
        items = [{"product_id": "notebook", "quantity": 1}]
        self.service.place_order("regular", items)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Quantity must be an integer"):
            self.service.place_order("regular", [{"product_id": "notebook", "quantity": 0}])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.service.place_order("regular", items)["order_id"], "ORD-0002")

    def test_reopened_cancelled_order_preserves_snapshot(self):
        items = [{"product_id": "pen-pack", "quantity": 2}]
        order = self.service.place_order("regular", items)
        reopened = OrderService(self.path)
        self.assertEqual(reopened.get_order(order["order_id"]), order)
        self.assertEqual(self.stock("pen-pack"), 8)
        cancelled = dict(order, status="cancelled")
        self.assertEqual(reopened.cancel_order(order["order_id"]), cancelled)
        self.assertEqual(OrderService(self.path).list_orders(), [cancelled])
        self.assertEqual(self.stock("pen-pack"), 10)

    def test_menu_declining_placement_leaves_state_untouched(self):
        output = StringIO()
        answers = ["3", "", "notebook", "2", "", "", "n", "0"]
        with patch("builtins.input", side_effect=answers), redirect_stdout(output):
            self.assertEqual(run_menu(self.service), 0)
        self.assertIn("Total: $10.00", output.getvalue())
        self.assertIn("Order not placed.", output.getvalue())
        self.assertFalse(self.path.exists())

    def test_repeat_cancellation_does_not_restore_stock_twice(self):
        items = [{"product_id": "pen-pack", "quantity": 2}]
        order = self.service.place_order("regular", items)
        cancelled = self.service.cancel_order(order["order_id"])
        before = self.path.read_bytes()
        self.assertEqual(self.service.cancel_order(order["order_id"]), cancelled)
        self.assertEqual(self.stock("pen-pack"), 10)
        self.assertEqual(self.path.read_bytes(), before)

    def stock(self, product_id):
        return next(product["stock"] for product in self.service.catalog() if product["product_id"] == product_id)
