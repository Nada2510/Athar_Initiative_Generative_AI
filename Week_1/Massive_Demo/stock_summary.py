import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

API_BASE = "https://api.massive.com"


@dataclass
class StockBar:
    ticker: str
    date: str
    open_price: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    trades: int | None = None

    @property
    def change(self) -> float:
        return self.close - self.open_price

    @property
    def change_pct(self) -> float:
        return self.change / self.open_price * 100 if self.open_price else 0.0

    @classmethod
    def from_api(cls, data: dict, ticker: str) -> "StockBar":
        """Build a StockBar from the parsed JSON response."""
        results = data.get("results")
        if not results:
            raise LookupError(f"No data returned for '{ticker}'. Check the ticker symbol.")
        bar = results[0]
        return cls(
            ticker=data.get("ticker") or bar.get("T", ticker),
            date=datetime.fromtimestamp(bar["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
            open_price=bar["o"],
            high=bar["h"],
            low=bar["l"],
            close=bar["c"],
            volume=bar["v"],
            vwap=bar.get("vw"),
            trades=bar.get("n"),
        )

    def summary(self) -> str:
        lines = [
            f"{self.ticker}: previous trading day ({self.date})",
            "-" * 40,
            f"Open   : ${self.open_price:,.2f}",
            f"High   : ${self.high:,.2f}",
            f"Low    : ${self.low:,.2f}",
            f"Close  : ${self.close:,.2f}",
            f"Change : {self.change:+.2f} ({self.change_pct:+.2f}%)",
            f"Volume : {self.volume:,.0f}",
        ]
        if self.vwap is not None:
            lines.append(f"VWAP   : ${self.vwap:,.2f}")
        if self.trades is not None:
            lines.append(f"Trades : {self.trades:,}")
        return "\n".join(lines)


def fetch_stock(ticker: str, api_key: str) -> StockBar:
    response = requests.get(
        f"{API_BASE}/v2/aggs/ticker/{ticker.upper()}/prev",
        params={"adjusted": "true", "apiKey": api_key},
        timeout=10,
    )
    response.raise_for_status()
    return StockBar.from_api(response.json(), ticker.upper())


HTTP_MESSAGES = {
    401: "The API key was rejected. Check MASSIVE_API_KEY in your .env file.",
    403: "Your plan does not include this data (HTTP 403).",
    404: "Ticker or endpoint not found (HTTP 404).",
    429: "Too many requests. The free plan is rate-limited, so wait a minute and retry.",
}


def main() -> int:
    load_dotenv()  # reads .env from the current directory
    api_key = os.getenv("MASSIVE_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("Error: MASSIVE_API_KEY is missing. Put your real key in the .env file.")
        return 1

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    try:
        print(fetch_stock(ticker, api_key).summary())
    except requests.HTTPError as err:
        # Never print `err` itself: its text contains the full URL, including the key.
        status = err.response.status_code if err.response is not None else None
        print(HTTP_MESSAGES.get(status, f"API error (HTTP {status})."))
        return 1
    except requests.RequestException as err:
        # Same reason: show only the error type, not the URL.
        print(f"Network error ({type(err).__name__}). Check your internet connection.")
        return 1
    except LookupError as err:
        print(err)
        return 1
    except (KeyError, TypeError, ValueError):
        print("Unexpected response format from the API.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
