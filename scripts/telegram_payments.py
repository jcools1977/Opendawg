#!/usr/bin/env python3
"""
Telegram Stars Payment Handler for Bot Arcade.

Integrates with the Telegram Bot Payments API using Stars (XTR currency).
Handles invoice generation, pre-checkout validation, and fulfillment.

No external dependencies — uses only urllib from Python stdlib.

Usage:
    python3 telegram_payments.py invoice <bot_token> <chat_id> <item_id>
    python3 telegram_payments.py checkout <bot_token> <query_id> <approve|deny>
    python3 telegram_payments.py fulfill <bot_token> <chat_id> <player_id> <item_id>
    python3 telegram_payments.py refund <bot_token> <user_id> <charge_id>
    python3 telegram_payments.py catalog
    python3 telegram_payments.py revenue

Environment:
    TELEGRAM_BOT_TOKEN  — Bot token from @BotFather (alternative to passing as arg)
    ARCADE_DATA_DIR     — Data directory (default: ~/.arcade)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

# --- Star Price Catalog ---
# All prices in Telegram Stars (1 Star ≈ $0.013-0.02 USD)
# Telegram takes ~30% on purchase, you get ~70% on withdrawal

CATALOG = {
    # === Premium Game Access ===
    "boss_raid_ticket": {
        "title": "Boss Raid Ticket",
        "description": "Join a Boss Raid battle! Fight epic bosses with your party for rare loot.",
        "stars": 5,
        "category": "game_access",
        "coins_bonus": 0,
        "type": "consumable",
    },
    "tournament_entry": {
        "title": "Tournament Entry Pass",
        "description": "Enter the competitive tournament bracket. Win the prize pool!",
        "stars": 10,
        "category": "game_access",
        "coins_bonus": 0,
        "type": "consumable",
    },
    "prediction_create": {
        "title": "Prediction Market Pass",
        "description": "Create a prediction market for your group. Social betting with virtual coins!",
        "stars": 3,
        "category": "game_access",
        "coins_bonus": 0,
        "type": "consumable",
    },

    # === Coin Packs ===
    "coins_starter": {
        "title": "Starter Coin Pack",
        "description": "200 Arcade Coins to get you rolling. Spin slots, enter games, buy cosmetics!",
        "stars": 5,
        "category": "coins",
        "coins_bonus": 200,
        "type": "consumable",
    },
    "coins_value": {
        "title": "Value Coin Pack",
        "description": "600 Arcade Coins — 20% bonus vs Starter! Best for regular players.",
        "stars": 12,
        "category": "coins",
        "coins_bonus": 600,
        "type": "consumable",
    },
    "coins_mega": {
        "title": "Mega Coin Pack",
        "description": "1,500 Arcade Coins — 50% bonus vs Starter! For the serious gamer.",
        "stars": 25,
        "category": "coins",
        "coins_bonus": 1500,
        "type": "consumable",
    },
    "coins_whale": {
        "title": "Whale Coin Pack",
        "description": "5,000 Arcade Coins — DOUBLE value vs Starter! Dominate the leaderboard.",
        "stars": 65,
        "category": "coins",
        "coins_bonus": 5000,
        "type": "consumable",
    },

    # === Extra Plays ===
    "extra_spins_5": {
        "title": "5 Extra Slot Spins",
        "description": "5 bonus slot machine spins today. Chase that jackpot!",
        "stars": 2,
        "category": "extras",
        "coins_bonus": 0,
        "type": "consumable",
    },
    "extra_scratches_3": {
        "title": "3 Extra Scratch Cards",
        "description": "3 bonus scratch cards today. Match 3 to win big!",
        "stars": 2,
        "category": "extras",
        "coins_bonus": 0,
        "type": "consumable",
    },
    "extra_fortune": {
        "title": "Bonus Fortune Reading",
        "description": "One extra fortune drop today. Will it be Legendary?",
        "stars": 1,
        "category": "extras",
        "coins_bonus": 0,
        "type": "consumable",
    },
    "streak_freeze": {
        "title": "Streak Freeze Token",
        "description": "Protect your daily streak! Skip one day without breaking your streak.",
        "stars": 3,
        "category": "extras",
        "coins_bonus": 0,
        "type": "consumable",
    },

    # === Cosmetics ===
    "theme_ocean": {
        "title": "Ocean Slot Theme",
        "description": "Themed slot reels with ocean emojis. Permanent unlock!",
        "stars": 5,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "theme_space": {
        "title": "Space Slot Theme",
        "description": "Themed slot reels with space emojis. Permanent unlock!",
        "stars": 5,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "theme_fantasy": {
        "title": "Fantasy Slot Theme",
        "description": "Themed slot reels with fantasy emojis. Dragons, swords, magic!",
        "stars": 8,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "border_flame": {
        "title": "Flame Profile Border",
        "description": "A fiery border around your player profile. Show off your heat!",
        "stars": 10,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "border_diamond": {
        "title": "Diamond Profile Border",
        "description": "A sparkling diamond border. Pure luxury for your profile.",
        "stars": 20,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "title_chosen_one": {
        "title": "Title: The Chosen One",
        "description": "Exclusive purchasable title displayed on your profile.",
        "stars": 15,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "title_neon_ghost": {
        "title": "Title: Neon Ghost",
        "description": "Exclusive purchasable title. Mysterious and rare.",
        "stars": 20,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },
    "title_arcade_royalty": {
        "title": "Title: Arcade Royalty",
        "description": "The most prestigious purchasable title. Crown yourself.",
        "stars": 35,
        "category": "cosmetic",
        "coins_bonus": 0,
        "type": "permanent",
    },

    # === Season Pass ===
    "season_pass": {
        "title": "Arcade Season Pass (30 days)",
        "description": "Premium rewards track, exclusive challenges, 2x daily coins, exclusive cosmetics for 30 days!",
        "stars": 50,
        "category": "subscription",
        "coins_bonus": 500,
        "type": "timed",
        "duration_days": 30,
    },

    # === Boss Raid Revival ===
    "raid_revival": {
        "title": "Boss Raid Revival",
        "description": "Revive your character mid-raid! Don't let your party down.",
        "stars": 2,
        "category": "game_access",
        "coins_bonus": 0,
        "type": "consumable",
    },
}


# --- Telegram API Helpers ---

def _tg_api(bot_token: str, method: str, payload: dict) -> dict:
    """Call a Telegram Bot API method."""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {"ok": False, "error": error_body, "status_code": e.code}
    except urllib.error.URLError as e:
        return {"ok": False, "error": str(e)}


def _get_token(args_token: str = None) -> str:
    """Get bot token from args or environment."""
    token = args_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(json.dumps({
            "error": "No bot token. Pass as argument or set TELEGRAM_BOT_TOKEN env var."
        }))
        sys.exit(1)
    return token


# --- Data Persistence ---

DATA_DIR = Path(os.environ.get("ARCADE_DATA_DIR", Path.home() / ".arcade"))
PAYMENTS_DIR = DATA_DIR / "payments"
PAYMENTS_DIR.mkdir(parents=True, exist_ok=True)

REVENUE_FILE = DATA_DIR / "revenue.json"


def _load_json(path: Path, default=None):
    if default is None:
        default = {}
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default


def _save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _record_payment(chat_id: str, player_id: str, item_id: str, stars: int):
    """Record a successful payment for analytics and fulfillment tracking."""
    revenue = _load_json(REVENUE_FILE, {
        "total_stars": 0,
        "total_transactions": 0,
        "transactions": [],
        "by_item": {},
        "by_player": {},
    })

    revenue["total_stars"] += stars
    revenue["total_transactions"] += 1

    transaction = {
        "chat_id": chat_id,
        "player_id": player_id,
        "item_id": item_id,
        "stars": stars,
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    revenue["transactions"].append(transaction)

    # Track by item
    if item_id not in revenue["by_item"]:
        revenue["by_item"][item_id] = {"count": 0, "total_stars": 0}
    revenue["by_item"][item_id]["count"] += 1
    revenue["by_item"][item_id]["total_stars"] += stars

    # Track by player
    if player_id not in revenue["by_player"]:
        revenue["by_player"][player_id] = {"count": 0, "total_stars": 0}
    revenue["by_player"][player_id]["count"] += 1
    revenue["by_player"][player_id]["total_stars"] += stars

    _save_json(REVENUE_FILE, revenue)
    return transaction


# --- Commands ---

def cmd_invoice(bot_token: str, chat_id: str, item_id: str):
    """Send a Telegram Stars payment invoice to a user."""
    if item_id not in CATALOG:
        print(json.dumps({
            "error": f"Unknown item: {item_id}",
            "available_items": list(CATALOG.keys())
        }))
        return

    item = CATALOG[item_id]
    token = _get_token(bot_token)

    # Telegram Stars invoice payload
    # provider_token is empty string for Stars
    # currency is "XTR" for Telegram Stars
    payload = {
        "chat_id": int(chat_id),
        "title": item["title"],
        "description": item["description"],
        "payload": json.dumps({
            "item_id": item_id,
            "player_id": chat_id,
            "type": item["type"],
        }),
        "provider_token": "",  # Empty for Telegram Stars
        "currency": "XTR",     # Telegram Stars currency code
        "prices": [
            {
                "label": item["title"],
                "amount": item["stars"],  # Stars amount (no decimal)
            }
        ],
    }

    result = _tg_api(token, "sendInvoice", payload)

    if result.get("ok"):
        print(json.dumps({
            "status": "invoice_sent",
            "item": item_id,
            "stars": item["stars"],
            "chat_id": chat_id,
            "message_id": result.get("result", {}).get("message_id"),
        }))
    else:
        print(json.dumps({
            "status": "error",
            "error": result.get("error", "Unknown error"),
            "item": item_id,
        }))


def cmd_checkout(bot_token: str, query_id: str, approve: str):
    """Respond to a pre_checkout_query (approve or deny)."""
    token = _get_token(bot_token)

    if approve.lower() in ("approve", "yes", "true", "1"):
        payload = {
            "pre_checkout_query_id": query_id,
            "ok": True,
        }
    else:
        payload = {
            "pre_checkout_query_id": query_id,
            "ok": False,
            "error_message": "Payment could not be processed. Please try again.",
        }

    result = _tg_api(token, "answerPreCheckoutQuery", payload)
    print(json.dumps({
        "status": "checkout_responded",
        "approved": approve.lower() in ("approve", "yes", "true", "1"),
        "result": result,
    }))


def cmd_fulfill(bot_token: str, chat_id: str, player_id: str, item_id: str):
    """
    Fulfill a successful payment — credit the player's account.

    Call this AFTER receiving a successful_payment message from Telegram.
    This credits coins, unlocks cosmetics, or grants access as appropriate.
    """
    if item_id not in CATALOG:
        print(json.dumps({"error": f"Unknown item: {item_id}"}))
        return

    item = CATALOG[item_id]
    fulfillment = {"item_id": item_id, "actions": []}

    # Record the payment
    _record_payment(chat_id, player_id, item_id, item["stars"])

    # Build arcade_engine commands to execute for fulfillment
    engine = "scripts/arcade_engine.py"
    commands = []

    # Credit bonus coins if applicable
    if item.get("coins_bonus", 0) > 0:
        # We'll output the command for the skill to execute
        fulfillment["actions"].append({
            "action": "credit_coins",
            "amount": item["coins_bonus"],
            "command": (
                f"python3 {engine} save {player_id} "
                f"'{json.dumps({'coins_delta': item['coins_bonus']})}'"
            ),
        })

    # Handle item-specific fulfillment
    if item["category"] == "game_access":
        fulfillment["actions"].append({
            "action": "grant_access",
            "item": item_id,
            "note": f"Player {player_id} granted access to {item['title']}",
        })

    elif item["category"] == "cosmetic":
        fulfillment["actions"].append({
            "action": "unlock_cosmetic",
            "item": item_id,
            "note": f"Permanently unlocked {item['title']} for {player_id}",
        })

    elif item["category"] == "extras":
        if "spins" in item_id:
            fulfillment["actions"].append({
                "action": "add_extra_spins",
                "amount": 5,
            })
        elif "scratches" in item_id:
            fulfillment["actions"].append({
                "action": "add_extra_scratches",
                "amount": 3,
            })
        elif "fortune" in item_id:
            fulfillment["actions"].append({
                "action": "reset_daily_fortune",
            })
        elif "streak" in item_id:
            fulfillment["actions"].append({
                "action": "add_streak_freeze",
                "amount": 1,
            })

    elif item["category"] == "subscription":
        fulfillment["actions"].append({
            "action": "activate_season_pass",
            "duration_days": item.get("duration_days", 30),
            "note": f"Season pass activated for {player_id}",
        })

    fulfillment["status"] = "fulfilled"
    fulfillment["stars_paid"] = item["stars"]
    fulfillment["estimated_usd"] = round(item["stars"] * 0.013, 2)

    # Send confirmation message to user
    token = _get_token(bot_token)
    confirm_msg = f"Payment confirmed! You received: {item['title']}"
    if item.get("coins_bonus", 0) > 0:
        confirm_msg += f" + {item['coins_bonus']} Arcade Coins"
    confirm_msg += "\n\nThank you for supporting Bot Arcade!"

    _tg_api(token, "sendMessage", {
        "chat_id": int(chat_id),
        "text": confirm_msg,
    })

    print(json.dumps(fulfillment, indent=2))


def cmd_refund(bot_token: str, user_id: str, charge_id: str):
    """Refund a Telegram Stars payment."""
    token = _get_token(bot_token)

    result = _tg_api(token, "refundStarPayment", {
        "user_id": int(user_id),
        "telegram_payment_charge_id": charge_id,
    })

    if result.get("ok"):
        print(json.dumps({
            "status": "refunded",
            "user_id": user_id,
            "charge_id": charge_id,
        }))
    else:
        print(json.dumps({
            "status": "error",
            "error": result.get("error", "Refund failed"),
        }))


def cmd_catalog():
    """Display the full item catalog with prices."""
    categories = {}
    for item_id, item in CATALOG.items():
        cat = item["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "id": item_id,
            "title": item["title"],
            "stars": item["stars"],
            "usd_approx": f"${item['stars'] * 0.013:.2f}",
            "type": item["type"],
            "description": item["description"],
        })

    print(json.dumps({
        "catalog": categories,
        "total_items": len(CATALOG),
        "currency": "Telegram Stars (XTR)",
        "note": "1 Star ≈ $0.013 USD. Bot receives ~70% after Telegram's cut.",
    }, indent=2))


def cmd_revenue():
    """Display revenue analytics."""
    revenue = _load_json(REVENUE_FILE, {
        "total_stars": 0,
        "total_transactions": 0,
        "transactions": [],
        "by_item": {},
        "by_player": {},
    })

    # Calculate derived stats
    total_usd = round(revenue["total_stars"] * 0.013, 2)
    operator_usd = round(total_usd * 0.7, 2)  # After Telegram's ~30% cut

    top_items = sorted(
        revenue.get("by_item", {}).items(),
        key=lambda x: x[1]["total_stars"],
        reverse=True,
    )[:5]

    top_players = sorted(
        revenue.get("by_player", {}).items(),
        key=lambda x: x[1]["total_stars"],
        reverse=True,
    )[:5]

    # Recent transactions (last 10)
    recent = revenue.get("transactions", [])[-10:]

    print(json.dumps({
        "summary": {
            "total_stars_earned": revenue["total_stars"],
            "total_transactions": revenue["total_transactions"],
            "gross_revenue_usd": total_usd,
            "net_revenue_usd": operator_usd,
            "telegram_cut_usd": round(total_usd - operator_usd, 2),
        },
        "top_items": [
            {"item": k, "sales": v["count"], "stars": v["total_stars"]}
            for k, v in top_items
        ],
        "top_spenders": [
            {"player": k, "purchases": v["count"], "stars": v["total_stars"]}
            for k, v in top_players
        ],
        "recent_transactions": recent,
    }, indent=2))


# --- Main Entry Point ---

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "No command specified.",
            "usage": {
                "invoice": "invoice <bot_token> <chat_id> <item_id>",
                "checkout": "checkout <bot_token> <query_id> <approve|deny>",
                "fulfill": "fulfill <bot_token> <chat_id> <player_id> <item_id>",
                "refund": "refund <bot_token> <user_id> <charge_id>",
                "catalog": "catalog",
                "revenue": "revenue",
            }
        }))
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "invoice":  (cmd_invoice,  3),
        "checkout": (cmd_checkout, 3),
        "fulfill":  (cmd_fulfill,  4),
        "refund":   (cmd_refund,   3),
        "catalog":  (cmd_catalog,  0),
        "revenue":  (cmd_revenue,  0),
    }

    if command not in commands:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)

    func, min_args = commands[command]
    if len(args) < min_args:
        print(json.dumps({"error": f"Not enough arguments for '{command}'"}))
        sys.exit(1)

    func(*args[:min_args + 2])


if __name__ == "__main__":
    main()
