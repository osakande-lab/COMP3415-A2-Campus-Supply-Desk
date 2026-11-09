"""Reproduce the follow-up AI review against the published service."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from supplydesk.service import OrderService


def line(product_id, quantity):
    return {"product_id": product_id, "quantity": quantity}


def stock(state, product_id):
    return next(p["stock"] for p in state["catalog"] if p["product_id"] == product_id)


def check_review(service):
    for items in ([line("notebook", 8), line("pen-pack", 1)],
                  [line("notebook", 10)],
                  [line("notebook", 9), line("pen-pack", 1)]):
        result = service.quote("student", items)
        print("Student subtotal / discount:", result["subtotal_cents"], result["discount_cents"])

    items = [line("notebook", 12), line("notebook", 9)]
    quote = service.quote("regular", items)
    print("Quote accepts duplicate lines totaling:", sum(p["quantity"] for p in quote["items"]))
    service.place_order("regular", items)
    print("Persisted notebook stock after placement:", stock(service.store.load(), "notebook"))


class QuoteBasedPlacement(OrderService):
    """Isolate the proposed replacement without changing production code."""

    def _price_request(self, catalog, customer_type, items, fulfillment):
        return self.quote(customer_type, items, fulfillment)

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return OrderService._price_request(self, state["catalog"], customer_type, items, fulfillment)


def check_snapshots(path):
    state = OrderService(path).store.load()
    older = deepcopy(state)
    next(p for p in older["catalog"] if p["product_id"] == "notebook")["stock"] = 1
    for cls in (OrderService, QuoteBasedPlacement):
        service = cls(path)
        with patch.object(service.store, "load", side_effect=[deepcopy(older), deepcopy(state)]) as load:
            with patch.object(service.store, "save") as save:
                try:
                    service.place_order("regular", [line("notebook", 2)])
                except ValueError as error:
                    outcome = str(error)
                else:
                    outcome = f"saved notebook stock {stock(save.call_args.args[0], 'notebook')}"
                print(f"{cls.__name__}: {load.call_count} reads, {save.call_count} saves, {outcome}")


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        path = Path(directory) / "state.json"
        check_snapshots(path)
        check_review(OrderService(path))
