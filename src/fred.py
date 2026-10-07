"""Provider metadata verification: fail closed before assigning FX direction."""
import re
from html import unescape
from .validation import DataError


def verify_eurusd_metadata(page):
    text = unescape(re.sub(r"<[^>]+>", " ", page))
    text = " ".join(text.split())
    if "DEXUSEU" not in text or not re.search(r"Units\s*:\s*U\.S\. Dollars to One Euro", text):
        raise DataError("FRED DEXUSEU units could not be verified as USD per EUR.")
    return dict(units="USD per EUR", currency="USD", base="EUR", quote="USD",
                direction_evidence="U.S. Dollars to One Euro", identity_evidence="provider_metadata")
