from app.anonymize import PiiVault, contains_pii


def test_masks_phone_and_email_with_stable_tokens():
    vault = PiiVault()
    masked = vault.mask("Call +380 67 123 45 67 or write olena.k@example.com, again: +380 67 123 45 67")
    assert masked == "Call [PHONE_1] or write [EMAIL_1], again: [PHONE_1]"
    assert not contains_pii(masked)


def test_unmask_restores_values_in_tool_args():
    vault = PiiVault()
    vault.mask("my number is 067-123-45-67")
    assert vault.unmask_args({"phone": "[PHONE_1]", "rooms": 2}) == {"phone": "067-123-45-67", "rooms": 2}


def test_leaves_dates_prices_and_listing_ids_alone():
    vault = PiiVault()
    text = "KH-101 on 2026-11-03 10:00 for 1400 USD"
    assert vault.mask(text) == text


def test_local_formats():
    vault = PiiVault()
    assert vault.mask("(093) 555 66 77") == "[PHONE_1]"
    assert vault.mask("0501112233") == "[PHONE_2]"
