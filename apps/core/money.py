"""Uang selalu integer rupiah. Format tampilan: `Rp 1.250.000`."""


def format_rupiah(amount) -> str:
    if amount is None or amount == "":
        return ""
    value = int(amount)
    text = f"{abs(value):,}".replace(",", ".")
    return f"-Rp {text}" if value < 0 else f"Rp {text}"
