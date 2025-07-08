"""
This script gets BTC related indexes through API calls to help with buy strategies.

Usage: Execute the btc-indexes.py script. Logging files will be saved in "/tmp/btc_dash".
"""

import requests
import math
from datetime import datetime
import time
import sys
import logging
import os

# Const to enable logging
ENABLE_LOGGER = False

# Base timeout for requests
TIMEOUT = 3

# URLs for fetching relevant data
URL_BTC_PRICE = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
URL_BTC_INFO = "https://api.coingecko.com/api/v3/coins/bitcoin"
URL_BTC_PRICE_RANGE = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
URL_FEAR_GREED = "https://api.alternative.me/fng/?limit=1"
URL_TRANSFER_FEES = "https://mempool.space/api/v1/fees/recommended"

# Thresholds for signals
MAYER_BUY_THRESHOLD = 1.0
FEAR_GREED_BUY_THRESHOLD = 25
FEE_TRANSFER_THRESHOLD = 15


def get_btc_price():
    """Get the current price of BTC in USD."""
    price = None
    
    try:
        resp = requests.get(URL_BTC_PRICE, timeout=TIMEOUT)
        resp.raise_for_status()
        
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object.")
        
        btc_data = data.get("bitcoin")
        if not isinstance(btc_data, dict):
            raise ValueError("Missing or invalid 'bitcoin' field.")
        
        price = btc_data.get("usd")
        
        if not isinstance(price, (int, float)):
            raise ValueError("Price is missing or not a number.")
        
    except requests.exceptions.RequestException:
        log_exception("Request error while fetching BTC price")
    except ValueError:
        log_exception("Invalid value received for BTC price")
    except Exception:
        log_exception("Unexpected error occurred while fetching BTC price")
    finally:
        return price

def get_btc_ath():
    """Get BTC all time high price."""
    ath_usd = None
    
    try:
        resp = requests.get(URL_BTC_INFO, timeout=TIMEOUT)
        resp.raise_for_status()
        
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object.")

        market_data = data.get("market_data")
        if not isinstance(market_data, dict):
            raise ValueError("Missing or invalid 'market_data'.")

        ath = market_data.get("ath")
        if not isinstance(ath, dict):
            raise ValueError("Missing or invalid 'ath' field.")

        ath_usd = ath.get("usd")
        if not isinstance(ath_usd, (int, float)):
            raise ValueError("ATH value is missing or not a number.")

    except requests.exceptions.RequestException:
        log_exception("Request error while fetching BTC ATH")
    except ValueError:
        log_exception("Invalid data format received for BTC ATH")
    except Exception:
        log_exception("Unexpected error occurred while fetching BTC ATH")
    finally:
        return ath_usd

def get_200_day_ma():
    """Fetch BTC price data and calculate the 200-day moving average (MA200) in USD."""
    ma200 = None
    
    try:
        end_date = int(time.time())
        start_date = end_date - (200 * 86400)  # 200 days in seconds

        params = {
            "vs_currency": "usd",
            "from": start_date,
            "to": end_date
        }

        resp = requests.get(URL_BTC_PRICE_RANGE, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        
        data = resp.json()
        if not isinstance(data, dict) or "prices" not in data:
            raise ValueError("Missing or invalid 'prices' data in response.")
        
        prices_raw = data.get("prices")
        if not isinstance(prices_raw, list) or not prices_raw:
            raise ValueError("'prices' is empty or not a list.")

        prices = [item[1] for item in prices_raw]
        if not prices:
            raise ValueError("No valid price data found for calculation.")

        ma200 = sum(prices) / len(prices)
        
        ma200 = math.floor(ma200)

    except requests.exceptions.RequestException:
        log_exception("Request error while fetching BTC price range for MA200")
    except ValueError:
        log_exception("Invalid value or structure in BTC price data")
    except Exception:
        log_exception("Unexpected error occurred during MA200 calculation")
    finally:
        return ma200


def get_fear_and_greed():
    """Get the current Fear and Greed Index (value and label)."""
    value, label = None, None

    try:
        resp = requests.get(URL_FEAR_GREED, timeout=TIMEOUT)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, dict) or "data" not in data:
            raise ValueError("Response is missing expected 'data' field.")

        fg_items = data["data"]
        if not isinstance(fg_items, list) or not fg_items:
            raise ValueError("'data' field is not a non-empty list.")

        fg = fg_items[0]
        if not isinstance(fg, dict):
            raise ValueError("First element of 'data' is not a valid object.")

        value_raw = fg.get("value")
        label = fg.get("value_classification")

        if value_raw is None or label is None:
            raise ValueError("'value' or 'value_classification' missing in data.")

        value = int(value_raw)  # Coerce to int for safety

    except requests.exceptions.RequestException:
        log_exception("Request error while fetching Fear and Greed index")
    except ValueError:
        log_exception("Invalid or missing values in Fear and Greed response")
    except Exception:
        log_exception("Unexpected error occurred while fetching Fear and Greed index")
    finally:
        return value, label

def get_transfer_fees():
    """Get Bitcoin transfer fees (fastest, half-hour, hour) in sat/vB."""
    new_fees = {
        "fastestFee": None,
        "halfHourFee": None,
        "hourFee": None
    }

    try:
        resp = requests.get(URL_TRANSFER_FEES, timeout=TIMEOUT)
        resp.raise_for_status()
        
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Response is not a valid JSON object.")
        
        # Extract and validate individual fee values
        for key in new_fees:
            value = data.get(key)
            if isinstance(value, (int, float)):
                new_fees[key] = value
            else:
                logging.warning(f"⚠️ Missing or invalid value for '{key}' in fee data.")

    except requests.exceptions.RequestException:
        log_exception("Request error while fetching transfer fees")
    except ValueError:
        log_exception("Invalid response structure for transfer fees")
    except Exception:
        log_exception("Unexpected error occurred while fetching transfer fees")
    finally:
        return new_fees

def calculate_mayer_index(price, moving_average):
    """Calculate the Mayer index using price and moving average values."""
    return round(price / moving_average, 2) if price and moving_average else None

def check_print(value):
    """Check value for print. Returns '--' if None."""
    return "--" if value is None else value

def clear_all(hide_cursor=True):
    """Clear all the lines in the terminal window."""
    sys.stdout.write("\033[2J\033[H")   # Clear all lines
    
    # Toggle Show/Hide cursor
    sys.stdout.write("\033[?25l") if hide_cursor else sys.stdout.write("\033[?25h")
    
    sys.stdout.flush()

def print_header():
    """Header to be print at the start of the script."""
    print("▄▄███▄▄·██████╗ ████████╗ ██████╗██████╗  █████╗ ███████╗██╗  ██╗")
    print("██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║")
    print("███████╗██████╔╝   ██║   ██║     ██║  ██║███████║███████╗███████║")
    print("╚════██║██╔══██╗   ██║   ██║     ██║  ██║██╔══██║╚════██║██╔══██║")
    print("███████║██████╔╝   ██║   ╚██████╗██████╔╝██║  ██║███████║██║  ██║")
    print("╚═▀▀▀══╝╚═════╝    ╚═╝    ╚═════╝╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝")
    print()

def clear_terminal_lines(n=10):
    """Clear a specific number of lines in the terminal window. 10 lines as default."""
    for _ in range(n):
        # Move cursor up one line and clear the line
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[K")

def check_indexes(price, btc_ath, ma200, mayer, fear_value, fees):
    """Check the input indexes to return fitting messages related to them."""
    lines = 0
    message = ''
    
    # Validate required inputs
    missing_data = any(
        x is None for x in [price, btc_ath, ma200, mayer, fear_value, fees]
    )
    
    # Extract fee safely
    half_hour_fee = fees.get('halfHourFee') if isinstance(fees, dict) else None
    
    # ✅ Buy Signal: Mayer < 1.0 and Fear & Greed <= 25
    if isinstance(mayer, (int, float)) and mayer < MAYER_BUY_THRESHOLD and \
       isinstance(fear_value, (int, float)) and fear_value <= FEAR_GREED_BUY_THRESHOLD:
           message += "\n✅ BUY SIGNAL: Conditions favorable for lump buy!"
           lines += 1
    
    # ✅ Transfer Signal: Fee <= 15 sat/vB
    if isinstance(half_hour_fee, (int, float)) and half_hour_fee <= FEE_TRANSFER_THRESHOLD:
        message += "\n✅ TRANSFER SIGNAL: Conditions favorable for transfer on-chain!"
        lines += 1

    # ⚠️ Missing or invalid data
    if missing_data:
        message += "\n⚠️ Failed to fetch some data."
        lines+= 1

    # No alerts or issues
    if not message:
        message = "\nℹ️ No specific signals at this time."
        lines += 1

    return message, lines

def setup_logger():
    """Basic setup for logging."""
    log_dir = "/tmp/btc_dash"
    os.makedirs(log_dir, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
    file_name = os.path.join(log_dir, f"{date_str}.log")
    
    logging.basicConfig(level=logging.WARNING, filename=file_name, filemode="w",
                        format="%(asctime)s - %(levelname)s - %(message)s")

    logging.getLogger(__name__)
    
    logging.info("Logging set!")

def log_exception(message):
    """Log exception if the logger const is set to enable equal true"""
    if ENABLE_LOGGER:
        logging.exception(message)


if __name__ == '__main__':
    # Create/clear logging file
    if ENABLE_LOGGER:
        setup_logger()

    # Header print
    clear_all(hide_cursor=True)
    print_header()

    # Main Loop
    try:
        while True:
            print("Fetching data...")
            
            # Fetch and prepare data
            price = get_btc_price()
            btc_ath = get_btc_ath()
            ma200 = get_200_day_ma()
            mayer = calculate_mayer_index(price, ma200)

            fear_value, fear_label = get_fear_and_greed()
            fees = get_transfer_fees()

            # Clear console
            clear_terminal_lines(1)

            # Print new data
            print(f"🔸 BTC Price:       ${check_print(price)}")
            print(f"🔸 BTC ATH:         ${check_print(btc_ath)}")
            print(f"🔸 200-day MA:      ${check_print(ma200)}")
            print(f"🔸 Mayer Multiple:  {check_print(mayer)}")
            print(f"🔸 Fear & Greed:    {check_print(fear_value)} ({check_print(fear_label)})")
            print(f"🔸 Fees (sat/vB):   [Fast] {check_print(fees['fastestFee'])}, [Normal] {check_print(fees['halfHourFee'])}, [Cheap] {check_print(fees['hourFee'])}")

            warn_message, lines = check_indexes(price, btc_ath, ma200, mayer, fear_value, fees)

            print(warn_message)

            # Fetch data again each 1/2 hour - 1800
            time.sleep(1800)
            clear_terminal_lines(lines + 7)

    except KeyboardInterrupt:
        print("\nExiting script...\n")
    except Exception as e:
        print("\nSomething unexpected happened: ", e)
    finally:
        # Clear the terminal screen and show cursor when exiting script
        clear_all(hide_cursor=False)