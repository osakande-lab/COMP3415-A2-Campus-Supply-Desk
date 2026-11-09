"""Acceptance tests for CR-01 across service and terminal interfaces."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from supplydesk.cli import main
from supplydesk.menu import run_menu
from supplydesk.service import OrderService


class ExpressTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_client_pricing_examples(self):
        examples = [
            ("regular", "notebook", 2, 1000, 0, 2200),
            ("student", "hoodie", 2, 8000, 800, 8400),
            ("regular", "hoodie", 3, 12000, 0, 13200),
        ]
        for customer, product, quantity, subtotal, discount, total in examples:
            with self.subTest(customer=customer, product=product, quantity=quantity):
                quote = self.service.quote(
                    customer, [{"product_id": product, "quantity": quantity}], "express"
                )
                self.assertEqual(quote["fulfillment"], "express")
                self.assertEqual(quote["subtotal_cents"], subtotal)
                self.assertEqual(quote["discount_cents"], discount)
                self.assertEqual(quote["delivery_cents"], 1200)
                self.assertEqual(quote["total_cents"], total)
        standard = self.service.quote(
            "regular", [{"product_id": "hoodie", "quantity": 3}], "delivery"
        )
        self.assertEqual((standard["delivery_cents"], standard["total_cents"]), (0, 12000))
        self.assertFalse(self.path.exists())

    def test_order_snapshot_survives_reopen_and_cancellation(self):
        items = [{"product_id": "hoodie", "quantity": 2}]
        catalog = self.service.catalog()
        quote = self.service.quote("student", items, "express")
        order = self.service.place_order("student", items, "express")
        self.assertEqual({key: order[key] for key in quote}, quote)
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(self.service.get_order(order["order_id"]), order)
        reopened = OrderService(self.path)
        self.assertEqual(reopened.get_order(order["order_id"]), order)
        cancelled = dict(order, status="cancelled")
        self.assertEqual(reopened.cancel_order(order["order_id"]), cancelled)
        self.assertEqual(reopened.cancel_order(order["order_id"]), cancelled)
        self.assertEqual(OrderService(self.path).list_orders(), [cancelled])
        self.assertEqual(reopened.catalog(), catalog)

    def test_unknown_fulfillment_is_rejected(self):
        items = [{"product_id": "notebook", "quantity": 2}]
        for operation in (self.service.quote, self.service.place_order):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(ValueError, "Fulfillment must be"):
                    operation("regular", items, "overnight")
        self.assertFalse(self.path.exists())

    def test_cli_quote_and_place_accept_express(self):
        for command in ("quote", "place"):
            with self.subTest(command=command):
                output = StringIO()
                with redirect_stdout(output):
                    status = main([
                        "--data", str(self.path), command, "--customer", "student",
                        "--fulfillment", "express", "--item", "hoodie:2",
                    ])
                self.assertEqual(status, 0)
                result = json.loads(output.getvalue())
                self.assertEqual(result["fulfillment"], "express")
                self.assertEqual(result["total_cents"], 8400)

    def test_menu_quote_and_confirmed_placement_accept_express(self):
        request = ["", "notebook", "2", "", "express"]
        output = StringIO()
        with patch("builtins.input", side_effect=["2", *request, "3", *request, "y", "0"]) as read:
            with redirect_stdout(output):
                self.assertEqual(run_menu(self.service), 0)
        self.assertTrue(any("pickup/delivery/express" in call.args[0] for call in read.call_args_list))
        self.assertIn("Quote only", output.getvalue())
        self.assertIn("Total: $22.00", output.getvalue())
        orders = self.service.list_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual((orders[0]["fulfillment"], orders[0]["total_cents"]), ("express", 2200))
