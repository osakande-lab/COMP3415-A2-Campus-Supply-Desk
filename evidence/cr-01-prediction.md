# CR-01 prediction before implementation

Express will be accepted alongside pickup and standard delivery. Its fee will always be 1,200 cents, even if standard delivery would be free. I expect to update OrderService._price_request in supplydesk/service.py, build_parser in supplydesk/cli.py, read_request in supplydesk/menu.py, and the README and functional specification. I expect JSON storage and order retrieval to work with the existing fulfillment and price fields.

I plan to test all three client examples, quote and placement agreement, reopening and cancellation, rejection of unknown fulfillment values, and express through both terminal interfaces. I will rerun the baseline tests to check pickup, standard delivery, stock and history.
