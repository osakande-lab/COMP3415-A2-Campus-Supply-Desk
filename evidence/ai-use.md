# AI-use record

**Interaction:** ChatGPT follow-up review of the implementation in commit `dfb800e`.
This review took place after implementation. The AI excerpt below is from the
follow-up chat. The decisions are the outcomes of the evidence checks run for
that review. No production changes were made.

**ChatGPT response (excerpt, verbatim):**

> The review found two concrete gaps the 15 passing tests missed. I recommend testing student pickup at $49.50, $50.00, and $50.50 against the written discount rule. For repeated products, I recommend checking cumulative stock by product ID while keeping the original lines in the order. I’ll also test a plausible shortcut: have placement call the public `quote()` method directly. The question is whether that shares the calculation safely or makes placement read two different snapshots.

## Evaluation and decisions

### Modify the student discount boundary check

Use the existing catalog for the reproduction. Its item prices are multiples
of 250 cents, so the proposed $49.50 and $50.50 baskets cannot be built. The
probe uses $47.50, $50.00 and $52.50 instead. The spec says the 10% discount
starts at $50.00. The service used a strict greater-than check, giving 0 cents
at exactly $50.00 instead of 500. The $52.50 basket received 525 cents. The
boundary defect is documented and the production pricing rule was left in
place during this review.

### Accept cumulative stock as the right validation rule

The functional spec checks the total requested quantity by product. Two lines
of 12 and 9 notebooks passed individually against 20 in stock. The quote
accepted 21 and placement persisted stock of -1. This confirms why validation
should track the running quantity for each product while preserving separate
lines in the response. The review adds a reproduction. The production change
would be a separate bug-fix decision.

### Reject calling public quote from placement

This would reuse the public pricing entry point, but quote loads from storage
itself. Placement also needs the state it will update and save. The probe
models the proposed change with a subclass and supplies two different snapshots.
The first has one notebook and the second has 20. For an order of two, the
current service read once and rejected the order without saving. The proposed
shortcut read twice, validated against 20 and saved -1 against the first
snapshot. The mock shows a consequence if the reads differ. It makes no claim
about the frequency of concurrent writes. The current shared pricing helper
was kept because placement can validate and update using the same snapshot.

## Reproduction

From the repository root, run:

```sh
PYTHONPATH=. python evidence/review_checks.py
python -m unittest discover -s tests
```

Observed review output:

```text
OrderService: 1 reads, 0 saves, Not enough stock for notebook.
QuoteBasedPlacement: 2 reads, 1 saves, saved notebook stock -1
Student subtotal / discount: 4750 0
Student subtotal / discount: 5000 0
Student subtotal / discount: 5250 525
Quote accepts duplicate lines totaling: 21
Persisted notebook stock after placement: -1
```

The existing suite passed 15 tests. The reproduction deliberately reports
the observed defects using temporary storage and a mocked snapshot sequence.
