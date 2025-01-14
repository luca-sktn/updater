import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events, connection
from solders.keypair import Keypair  # type: ignore
from solanatracker import SolanaTracker
from discord_webhook import DiscordWebhook, DiscordEmbed
import aiohttp
import os
import re
from colorama import Fore, Style, init
import ctypes
import time
import requests
import wget
import sys
import subprocess
import random

init()


# AUTOUPDATER ###########################################################################################################

with open("settings.json", "r") as f:
    settings = json.load(f)

key = settings["key"]["runkey"]

if key == "dickdestroyer69420":
    print(Fore.GREEN + "Access Granted!")
else:
    print(Fore.RED + "Access Denied!")
    time.sleep(2)
    sys.exit()

version = "0.3.1"

# Get download link
try:
    dl = requests.get("https://raw.githubusercontent.com/luca-sktn/updater/refs/heads/main/downloadlink.txt")
    download_link = dl.text.strip()
except requests.exceptions.RequestException as e:
    print(Fore.RED + "Failed to fetch Download Link.")
    print(e)
    sys.exit(1)

# Get the latest version
try:
    v = requests.get("https://raw.githubusercontent.com/luca-sktn/updater/refs/heads/main/verision.txt")
    new_v = v.text.strip()
except requests.exceptions.RequestException as e:
    print(Fore.RED + "Failed to fetch version information.")
    print(e)
    time.sleep(2)
    sys.exit(1)

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

# Clear console before any logging
clear_console()
print(Fore.LIGHTWHITE_EX + "Checking for Updates...")

if version == new_v:
    print(Fore.MAGENTA + "No Update Available!")
    time.sleep(2)
    clear_console()
else:
    print(Fore.MAGENTA + "Update Available!")
    print(Fore.LIGHTBLUE_EX + "Downloading...")

    url = download_link
    try:
        wget.download(url, "InsiderNewVersion.exe")
    except Exception as e:
        print(Fore.RED + "Failed to download the update.")
        print(e)
        time.sleep(2)
        sys.exit(1)

    # Ensure the file was downloaded
    if not os.path.isfile("InsiderNewVersion.exe"):
        print(Fore.RED + "Download failed. File not found.")
        time.sleep(2)
        sys.exit(1)

    file_name = f"InsidersOnly {new_v}.exe"

    # Check if the new file name is valid
    if ":" in file_name or "\\" in file_name or "/" in file_name:
        print(Fore.RED + "Invalid characters in file name.")
        time.sleep(2)
        sys.exit(1)

    try:
        os.rename("InsiderNewVersion.exe", file_name)
        clear_console()
        print(Fore.LIGHTGREEN_EX + "Successfully Downloaded Newest Version!")
        time.sleep(0.5)
        print(Fore.LIGHTBLUE_EX + "Starting new version...")
        subprocess.Popen([file_name])
        time.sleep(2)
        print(Fore.YELLOW + "Closing old version...")
        time.sleep(4)
        sys.exit()
    except OSError as e:
        print(Fore.RED + "Failed to rename or start the new version.")
        print(e)
        sys.exit(1)

########################################################################################################################

# Load settings from settings.json
with open("settings.json", "r") as f:
    settings = json.load(f)

JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6/quote"

# Telegram Configuration for multiple clients
TELEGRAM_CLIENTS = settings["telegram"]["clients"]

# Solana Configuration
KEYPAIR = Keypair.from_base58_string(settings["solana"]["keypair"])
RPC_URL = settings["solana"]["rpc_url"]
PRIO_FEE = float(settings["solana"]["prio_fee"])
BUY_SLIPPAGE = int(settings["solana"]["buy_slipage"])
SELL_SLIPPAGE = int(settings["solana"]["sell_slippage"])

# Webhook URLs
SESSION_START_WEBHOOK_URL = settings["webhooks"]["session_start"]
BUY_WEBHOOK_URL = settings["webhooks"]["buy"]
SELL_WEBHOOK_URL = settings["webhooks"]["sell"]
ERROR_WEBHOOK_URL = settings["webhooks"]["error"]  # For buy/sell error logging
USER_NAME = settings["webhooks"]["name"]

# Groups Config Path
GROUPS_CONFIG_PATH = settings["paths"]["groups_config"]

# Contract file and initial balance
CONTRACTS_FILE = "contracts_bought.txt"
initial_balance = 0
trade_count = 0
current_balance = 0

# set cli title
ctypes.windll.kernel32.SetConsoleTitleW("InsidersOnly | TelegramSniper | User: " + USER_NAME)

# Set to track processed transactions (chat_id, message_id)
processed_transactions = set()
processed_transactions_lock = asyncio.Lock()

# Cache for Mint Decimals, in case we buy/sell the same Mint multiple times
mint_decimals_cache = {}

# Global aiohttp session
session = None

# Initialize SolanaTracker
solana_tracker = SolanaTracker(KEYPAIR, RPC_URL)
last_price_check = 0

# ---------------------------------------------------
async def get_decimals_for_mint(mint_address: str) -> int:
    # Check if already in cache
    if mint_address in mint_decimals_cache:
        return mint_decimals_cache[mint_address]

    # RPC Payload:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [
            mint_address,
            {
                "encoding": "jsonParsed"
            }
        ]
    }

    try:
        async with session.post(RPC_URL, json=payload) as resp:
            data = await resp.json()

            # Path: data["result"]["value"]["data"]["parsed"]["info"]["decimals"]
            decimals = data["result"]["value"]["data"]["parsed"]["info"]["decimals"]
            mint_decimals_cache[mint_address] = decimals
            return decimals

    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception fetching decimals for mint {mint_address}: {e}{Style.RESET_ALL}")
        # If it fails, take 9 as fallback
        return 9
# ---------------------------------------------------

# Welcome text
ascii_art = r"""
  ___         _    _             ___       _       
 |_ _|_ _  __(_)__| |___ _ _ ___/ _ \ _ _ | |_  _  
  | || ' \(_-| / _  / -_| '_(_-| (_) | ' \| | || | 
 |___|_||_/__|_\__,_\___|_| /__/\___/|_||_|_|\_, | 
                                             |__/
"""

# Version
VERSION = version

# Load group configurations
with open(GROUPS_CONFIG_PATH, "r") as f:
    groups_config = json.load(f)

group_names = [group["group_name"] for group in groups_config]

# Print welcome text
print(Fore.CYAN + ascii_art)
print(Fore.LIGHTCYAN_EX + f"Version: {VERSION}")
print("")
print(Fore.LIGHTWHITE_EX + f"Welcome {USER_NAME}!")
print(Fore.LIGHTWHITE_EX + "Enabled Groups:" + Fore.MAGENTA, ", ".join(group_names))
print("")
input(Fore.LIGHTWHITE_EX + "ENTER to Continue...")
print("")


async def is_valid_call(message, group_id):
    for group in groups_config:
        if group["group_id"] == group_id:
            call_keywords = group.get("call_keywords", [])
            stop_keywords = group.get("stop_keywords", [])
            # Check if all call keywords are present in the message
            if all(keyword in message for keyword in call_keywords):
                # Check if any stop keyword is present in the message
                if any(keyword in message for keyword in stop_keywords):
                    return False
                return True
    return False


async def extract_contract_address(message):
    lines = message.splitlines()
    
    # Regex for Solana addresses (43 or 44 Base58 characters)
    solana_address_pattern = re.compile(r'^[A-HJ-NP-Za-km-z1-9]{43,44}$')
    
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        
        # Check for "Contract:" or "CA:" or "🛒 Token Address:"
        if "Contract:" in stripped_line or "CA:" in stripped_line or "🛒 Token Address:" in stripped_line:
            parts = stripped_line.split(":")
            if len(parts) > 1:
                addr = parts[-1].strip().replace(" ", "")
                if addr and solana_address_pattern.match(addr):
                    return addr
            # If the address is in the next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip().replace(" ", "")
                if solana_address_pattern.match(next_line):
                    return next_line
        
        # Additional check for pure Solana addresses without prefix
        if solana_address_pattern.match(stripped_line):
            return stripped_line
    
    return None


# Function to add a contract address to the file
def add_contract_to_file(contract_address):
    with open(CONTRACTS_FILE, "a") as file:
        file.write(contract_address + "\n")


# Function to check if a contract address has already been bought
def is_contract_already_bought(contract_address):
    if os.path.exists(CONTRACTS_FILE):
        with open(CONTRACTS_FILE, "r") as file:
            contracts = file.read().splitlines()
            if contract_address in contracts:
                return True
    return False


# Function to verify transaction status
async def verify_transaction_status(txid):
    url = RPC_URL
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [str(txid), "jsonParsed"]  # Ensure txid is a string
    }
    for attempt in range(1, 76):  # Retry up to 15 times
        print(f"{Fore.YELLOW}[{datetime.now()}] Waiting for confirmation {attempt}/75 ...{Style.RESET_ALL}")
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["result"] is None:
                        print(f"{Fore.YELLOW}[{datetime.now()}] Transaction not confirmed yet.{Style.RESET_ALL}")
                    else:
                        meta = data["result"]["meta"]
                        if meta is None:
                            print(f"{Fore.RED}[{datetime.now()}] Transaction {txid} failed to confirm.{Style.RESET_ALL}")
                            return False
                        elif meta["err"] is None:
                            print(f"{Fore.GREEN}[{datetime.now()}] Transaction {txid} successfully confirmed.{Style.RESET_ALL}")
                            await update_current_balance()
                            return True
                        else:
                            error_details = meta["err"]
                            print(f"{Fore.RED}[{datetime.now()}] Transaction {txid} failed with error: {error_details}{Style.RESET_ALL}")
                            return False
                else:
                    response_text = await response.text()
                    print(f"{Fore.RED}[{datetime.now()}] Error checking transaction status: {response.status} - {response_text}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[{datetime.now()}] Exception while checking transaction status: {e}{Style.RESET_ALL}")
        await asyncio.sleep(0.45)  # Wait 2 seconds between retries
    print(f"{Fore.RED}[{datetime.now()}] Transaction {txid} not confirmed after 75 attempts.{Style.RESET_ALL}")
    return False


# Wallet Balance Check
async def check_wallet_balance():
    url = RPC_URL
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [str(KEYPAIR.pubkey())]
    }
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                balance = data.get("result", {}).get("value", 0) / 1e9  # Convert Lamports to SOL
                if balance <= 0:
                    print(f"{Fore.RED}[{datetime.now()}] Insufficient SOL in wallet: {balance} SOL{Style.RESET_ALL}")
                    await asyncio.sleep(1)
                    print(f"{Fore.RED}[{datetime.now()}] Exiting InsidersOnly...")
                    await asyncio.sleep(5)
                    exit(1)
                print(f"{Fore.GREEN}[{datetime.now()}] Wallet balance checked: {balance} SOL{Style.RESET_ALL}")
                ctypes.windll.kernel32.SetConsoleTitleW("InsidersOnly | TelegramSniper | User: " + USER_NAME + f" | Balance: {str(balance)} SOL")
                return balance
            else:
                response_text = await response.text()
                print(f"{Fore.RED}[{datetime.now()}] Error fetching wallet balance: {response.status} - {response_text}{Style.RESET_ALL}")
                await asyncio.sleep(1)
                print(f"{Fore.RED}[{datetime.now()}] Exiting InsidersOnly...")
                await asyncio.sleep(5)
                exit(1)
    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception while fetching wallet balance: {e}{Style.RESET_ALL}")
        await asyncio.sleep(1)
        print(f"{Fore.RED}[{datetime.now()}] Exiting InsidersOnly...")
        await asyncio.sleep(5)
        exit(1)


async def update_current_balance():
    global current_balance
    current_balance = await check_wallet_balance()


# Function to get token balance for a specific mint address using jsonParsed encoding
async def get_token_balance(token_mint_address):
    url = RPC_URL
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            str(KEYPAIR.pubkey()),
            {
                "mint": token_mint_address
            },
            {
                "encoding": "jsonParsed"
            }
        ]
    }
    try:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                token_accounts = data.get("result", {}).get("value", [])
                if not token_accounts:
                    print(f"{Fore.YELLOW}[{datetime.now()}] No token accounts found for mint {token_mint_address}.{Style.RESET_ALL}")
                    return 0
                total_balance = 0
                for account in token_accounts:
                    token_amount = account['account']['data']['parsed']['info']['tokenAmount']
                    ui_amount = token_amount.get('uiAmount', 0)
                    total_balance += ui_amount
                print(f"{Fore.GREEN}[{datetime.now()}] Verified token balance for {token_mint_address}: {total_balance} tokens{Style.RESET_ALL}")
                return total_balance
            else:
                response_text = await response.text()
                print(f"{Fore.RED}[{datetime.now()}] Error fetching token balance: {response.status} - {response_text}{Style.RESET_ALL}")
                return 0
    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception while fetching token balance: {e}{Style.RESET_ALL}")
        return 0


# Log received coins and return details
async def log_and_return_received_coins(response):
    amount_out = response["rate"]["amountOut"]  # Tokens received from swap response
    execution_price = response["rate"]["executionPrice"]  # Effective price per token
    fee = response["rate"]["fee"]  # Fees in SOL
    print(f"{Fore.CYAN}[{datetime.now()}] Received tokens (from response): {amount_out:.6f}, Effective price: {execution_price:.8f} SOL/token, Fees: {fee:.8f} SOL{Style.RESET_ALL}")
    return amount_out, execution_price, fee

# get token quote
async def get_token_quote(token_name, token_amount):
    # Fetch decimals via getAccountInfo:
    decimals = await get_decimals_for_mint(token_name)
    amount_in = int(token_amount * (10 ** decimals))

    url = JUPITER_QUOTE_API
    params = {
        "inputMint": token_name,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": amount_in,
        "slippageBps": SELL_SLIPPAGE
    }
    headers = {"Accept": "application/json"}

    # Load proxies from file
    try:
        with open("proxies.txt", "r") as f:
            proxies = f.read().strip().split("\n")
    except FileNotFoundError:
        print(f"{Fore.RED}[{datetime.now()}] proxies.txt not found.{Style.RESET_ALL}")
        return 0

    # Select a random proxy
    proxy = random.choice(proxies).strip()
    proxy_parts = proxy.split(":")
    if len(proxy_parts) != 4:
        print(f"{Fore.RED}[{datetime.now()}] Invalid proxy format in proxies.txt: {proxy}{Style.RESET_ALL}")
        return 0

    proxy_url = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"

    # Create a fresh session for each request
    connector = aiohttp.TCPConnector(ssl=False)  # Disable SSL verification (if needed)
    timeout = aiohttp.ClientTimeout(total=2)  # Timeout for the request
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        try:
            async with session.get(url, params=params, headers=headers, proxy=proxy_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if "outAmount" in data:
                        return float(data["outAmount"]) / 1e9  # Convert Lamports to SOL
                    else:
                        print(f"{Fore.RED}[{datetime.now()}] 'outAmount' not found in Jupiter response.{Style.RESET_ALL}")
                        return 0
                elif response.status == 400:
                    error_data = await response.json()
                    error_message = error_data.get("error", "Unknown error")
                    print(f"{Fore.RED}[{datetime.now()}] Error fetching quote: 400 - {error_message}{Style.RESET_ALL}")
                    return 0
                else:
                    response_text = await response.text()
                    print(f"{Fore.RED}[{datetime.now()}] Error fetching quote: {response.status} - {response_text}{Style.RESET_ALL}")
                    return 0
        except Exception as e:
            print(f"{Fore.RED}[{datetime.now()}] Exception while fetching Jupiter quote: {e}{Style.RESET_ALL}")
            return 0

# Monitor token price with rate limit handler and trailing TP/SL
async def monitor_token_price(token_name, received_coins, sell_profit, sell_loss, buy_amount, tip_fee):
    tp_counter = 0
    sl_counter = 0
    
    # Initialize trailing variables
    trailing_tp = buy_amount * (1 + sell_profit / 100)
    trailing_sl = buy_amount * (1 - sell_loss / 100)

    while True:
        try:
            current_value = await get_token_quote(token_name, received_coins)  # Use Jupiter API for quote
        except Exception as e:
            if '429' in str(e):
                print(f"{Fore.YELLOW}[{datetime.now()}] Rate limit exceeded. Waiting for 10 seconds before retrying.{Style.RESET_ALL}")
                await asyncio.sleep(10)
                continue
            else:
                print(f"{Fore.RED}[{datetime.now()}] Error: {e}{Style.RESET_ALL}")
                await asyncio.sleep(5)
                continue

        if current_value > 0:
            profit_loss = ((current_value - buy_amount) / buy_amount) * 100
            color = Fore.GREEN if profit_loss > 0 else Fore.RED
            print(f"{color}[{datetime.now()}] [{token_name}] Current PnL: {profit_loss:.2f}%{Style.RESET_ALL}")

            # Update trailing TP and SL dynamically
            if current_value > trailing_tp:
                trailing_tp = current_value * (1 + sell_profit / 100)
                trailing_sl = current_value * (1 - sell_loss / 100)
                print(f"{Fore.LIGHTBLUE_EX}[{datetime.now()}] Updated Trailing TP: {trailing_tp:.4f}, Trailing SL: {trailing_sl:.4f}{Style.RESET_ALL}")

            # Trailing Take-Profit Logic
            if current_value >= trailing_tp:
                tp_counter += 1
                sl_counter = 0  # Reset SL counter when TP condition is met
                print(f"{Fore.YELLOW}[{datetime.now()}] TP hit: {tp_counter}/3 [{profit_loss:.2f}% PnL]{Style.RESET_ALL}")

                if tp_counter == 3:
                    print(f"{Fore.GREEN}[{datetime.now()}] TakeProfit Executed - Selling [{token_name}]")
                    sell_success = await perform_sell(token_name, received_coins, buy_amount)
                    if sell_success:
                        break  # Exit monitoring loop if sell is successful
                    else:
                        print(f"{Fore.YELLOW}[{datetime.now()}] Retrying sell on next TP trigger.{Style.RESET_ALL}")
                    tp_counter = 0  # Reset the counter on sell failure

            # Trailing Stop-Loss Logic
            elif current_value <= trailing_sl:
                sl_counter += 1
                tp_counter = 0  # Reset TP counter when SL condition is met
                print(f"{Fore.RED}[{datetime.now()}] SL triggered: {sl_counter}/3 [{profit_loss:.2f}% PnL]{Style.RESET_ALL}")

                if sl_counter == 3:
                    print(f"{Fore.RED}[{datetime.now()}] StopLoss Executed - Selling [{token_name}]")
                    sell_success = await perform_sell(token_name, received_coins, buy_amount)
                    if sell_success:
                        break  # Exit monitoring loop if sell is successful
                    else:
                        print(f"{Fore.YELLOW}[{datetime.now()}] Retrying sell on next SL trigger.{Style.RESET_ALL}")
                    sl_counter = 0  # Reset the counter on sell failure

        await asyncio.sleep(0.55)  # Delay to respect Jupiter API rate limits

# Function to check token balance with retries after buy
async def check_token_balance_with_retries(token_name, max_retries=15, delay=2):
    for attempt in range(1, max_retries + 1):
        actual_balance = await get_token_balance(token_name)
        if actual_balance > 0:
            print(f"{Fore.GREEN}[{datetime.now()}] Token balance confirmed: {actual_balance} tokens{Style.RESET_ALL}")
            return actual_balance
        else:
            print(f"{Fore.YELLOW}[{datetime.now()}] Attempt {attempt}/{max_retries}: No tokens received yet. Retrying in {delay} seconds...")
            await asyncio.sleep(delay)
    print(f"{Fore.RED}[{datetime.now()}] No tokens received after {max_retries} attempts.{Style.RESET_ALL}")
    return 0


# Define a new function to log buy and sell errors to Discord
async def log_buy_sell_error(message):
    embed = DiscordEmbed(title="Info Notification", description=message, color=0xFF0000)
    await send_discord_webhook(embed, ERROR_WEBHOOK_URL)


# Sell tokens
async def perform_sell(token_name, sell_amount, buy_amount):
    global trade_count, processed_transactions
    swap_start_time = datetime.now()
    try:
        # Implementing timeout for perform_swap with increased duration
        try:
            swap_response = await asyncio.wait_for(
                solana_tracker.get_swap_instructions(
                    token_name,
                    "So11111111111111111111111111111111111111112",
                    sell_amount,
                    SELL_SLIPPAGE,  # Slippage
                    str(KEYPAIR.pubkey()),
                    PRIO_FEE  # Priority fee
                ),
                timeout=30  
            )
        except asyncio.TimeoutError:
            print(f"{Fore.RED}[{datetime.now()}] Sell transaction timed out while getting swap instructions.{Style.RESET_ALL}")
            await log_buy_sell_error(f"Sell transaction timed out while getting swap instructions for {token_name}.")
            return False

        try:
            txid = await asyncio.wait_for(
                solana_tracker.perform_swap(swap_response),
                timeout=20
            )
        except asyncio.TimeoutError:
            print(f"{Fore.RED}[{datetime.now()}] Sell transaction timed out while performing swap.{Style.RESET_ALL}")
            await log_buy_sell_error(f"Sell transaction timed out while performing swap for {token_name}.")
            return False

        swap_duration = datetime.now() - swap_start_time
        print(f"{Fore.CYAN}[{datetime.now()}] Transaction initiated: {txid}{Style.RESET_ALL}")

        if txid in processed_transactions:
            print(f"{Fore.YELLOW}[{datetime.now()}] Transaction {txid} has already been processed.{Style.RESET_ALL}")
            return False
        processed_transactions.add(txid)

        success = await verify_transaction_status(txid)
        if not success:
            print(f"{Fore.RED}[{datetime.now()}] Sell transaction failed. Returning to monitoring mode...{Style.RESET_ALL}")
            await log_buy_sell_error(f"Sell transaction {txid} failed for {token_name}.")
            return False  # Indicate failure to retry later

        # **Start of Balance Verification**
        # Fetch the actual token balance after sell transaction
        actual_balance = await get_token_balance(token_name)
        if actual_balance != 0:
            print(f"{Fore.RED}[{datetime.now()}] Discrepancy detected! Expected sell amount: {sell_amount}, Actual balance: {actual_balance}{Style.RESET_ALL}")
            # Optional: Decide whether to retry selling remaining tokens or handle differently
        else:
            print(f"{Fore.GREEN}[{datetime.now()}] Sell confirmed: Token balance is 0 as expected.{Style.RESET_ALL}")

        # Calculate profit/loss
        current_value = await get_token_quote(token_name, sell_amount)
        profit_loss = ((current_value - buy_amount) / buy_amount) * 100

        # Check for edge case where API returns incorrect sell value
        if current_value == 0:
            print(f"{Fore.RED}[{datetime.now()}] Error: Sell value returned as 0. Potential API issue.{Style.RESET_ALL}")
            await log_buy_sell_error(f"Sell value returned as 0 for {token_name}. Potential API issue.")
            profit_loss = -100.0

        # Increment trade count
        trade_count += 1

        # Send sell success webhook
        embed = DiscordEmbed(title="Sell Successful!", description=f"Token: {token_name}", color=0xFF0000)
        embed.add_embed_field(name="PnL", value=f"{profit_loss:.2f}%")
        embed.add_embed_field(name="Sell Value in SOL", value=f"{current_value:.6f} SOL")
        embed.add_embed_field(name="Initial Cost in SOL", value=f"{buy_amount:.6f} SOL")
        embed.add_embed_field(name="Swap Duration", value=f"{swap_duration}")
        embed.add_embed_field(name="Transaction", value=f"[View on Solscan](https://solscan.io/tx/{txid})")
        embed.add_embed_field(name="User", value=USER_NAME)
        await send_discord_webhook(embed, SELL_WEBHOOK_URL)

        # Add contract address to file
        add_contract_to_file(token_name)

        # Wait 15 seconds and send wallet balance webhook
        await asyncio.sleep(15)
        await send_wallet_balance_webhook()

        return True
    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception during perform_sell: {e}{Style.RESET_ALL}")
        await log_buy_sell_error(f"Exception during perform_sell for {token_name}: {e}")
        return False


# handle message
# handle_message event
async def handle_message(event):
    message = event.message.message
    group_id = event.chat_id
    message_id = event.message.id

    # Überprüfen, ob die Gruppe in groups_config existiert
    monitored_groups = [group["group_id"] for group in groups_config]
    if group_id not in monitored_groups:
        return  # Ignoriere Nachrichten aus nicht überwachten Gruppen

    # Generate a unique key for the message
    message_key = (group_id, message_id)

    # Synchronized access to processed_transactions
    async with processed_transactions_lock:
        if message_key in processed_transactions:
            # Nachricht wurde bereits verarbeitet, also loggen und beenden
            print(f"{Fore.LIGHTBLACK_EX}[{datetime.now()}] Message already received and processed: Group ID: {group_id}, Message ID: {message_id}.{Style.RESET_ALL}")
            return
        else:
            # Nachricht wird das erste Mal verarbeitet
            processed_transactions.add(message_key)

    # Nachricht weiter verarbeiten
    for group in groups_config:
        if group["group_id"] == group_id:
            # Check if the message is a valid call
            if await is_valid_call(message, group_id):
                print(f"{Fore.GREEN}[{datetime.now()}] Valid call detected in group {group_id}.{Style.RESET_ALL}")

                # Extract contract address logic
                for attempt in range(25):
                    try:
                        updated_message = await event.client.get_messages(entity=group_id, ids=message_id)
                        message_text = updated_message.message
                        contract_address = await extract_contract_address(message_text)
                    except Exception as e:
                        print(f"{Fore.RED}[{datetime.now()}] Error fetching the message: {e}{Style.RESET_ALL}")
                        await log_buy_sell_error(f"Error fetching the message from group {group_id}: {e}")

                    if contract_address:
                        print(f"{Fore.YELLOW}[{datetime.now()}] Extracted Contract Address: {contract_address}.{Style.RESET_ALL}")

                        # Check and add contract address to processed_transactions
                        async with processed_transactions_lock:
                            if is_contract_already_bought(contract_address):
                                print(f"{Fore.LIGHTBLACK_EX}[{datetime.now()}] Contract address {contract_address} has already been processed. Ignoring duplicate.{Style.RESET_ALL}")
                                return
                            else:
                                processed_transactions.add(contract_address)

                        # Load group parameters
                        buy_amount = group["buy_amount"]
                        sell_profit = group["sell_profit"]
                        sell_loss = group["sell_loss"]

                        # Check if the current balance is sufficient for the buy
                        if current_balance >= buy_amount:
                            await handle_token_swap(contract_address, buy_amount, sell_profit, sell_loss)
                        else:
                            print(f"{Fore.RED}[{datetime.now()}] Insufficient balance ({current_balance} SOL) for buying {buy_amount} SOL.{Style.RESET_ALL}")
                            await log_buy_sell_error(f"Insufficient balance: {current_balance} SOL. Required: {buy_amount} SOL.")
                        break
                    else:
                        print(f"{Fore.RED}[{datetime.now()}] No contract address found (Attempt {attempt + 1}/25).{Style.RESET_ALL}")
                        await asyncio.sleep(1.25)
            else:
                print(f"{Fore.RED}[{datetime.now()}] Message in group {group_id} is not a valid call.{Style.RESET_ALL}")

async def handle_token_swap(token_name, buy_amount, sell_profit, sell_loss):
    print(f"{Fore.GREEN}[{datetime.now()}] Detected token: {token_name}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[{datetime.now()}] Buying for {buy_amount} SOL, selling at +{sell_profit}% profit or -{sell_loss}% loss.{Style.RESET_ALL}")

    # Check if the contract address has already been bought
    if is_contract_already_bought(token_name):
        print(f"{Fore.RED}[{datetime.now()}] Contract address {token_name} already bought. Skipping purchase.{Style.RESET_ALL}")
        return

    swap_start_time = datetime.now()

    try:
        # Implementing timeout for perform_swap with increased duration
        try:
            swap_response = await asyncio.wait_for(
                solana_tracker.get_swap_instructions(
                    "So11111111111111111111111111111111111111112",
                    token_name,
                    buy_amount,
                    BUY_SLIPPAGE,  # Slippage
                    str(KEYPAIR.pubkey()),
                    PRIO_FEE  # Priority fee
                ),
                timeout=30  # Increased timeout
            )
        except asyncio.TimeoutError:
            print(f"{Fore.RED}[{datetime.now()}] Buy transaction timed out while getting swap instructions.{Style.RESET_ALL}")
            await log_buy_sell_error(f"Buy transaction timed out while getting swap instructions for {token_name}.")
            return

        try:
            txid = await asyncio.wait_for(
                solana_tracker.perform_swap(swap_response),
                timeout=30  # Increased timeout
            )
        except asyncio.TimeoutError:
            print(f"{Fore.RED}[{datetime.now()}] Buy transaction timed out while performing swap.{Style.RESET_ALL}")
            await log_buy_sell_error(f"Buy transaction timed out while performing swap for {token_name}.")
            return

        # **New Section: Check Swap Response**
        # Here we check if the response from perform_swap indicates an error or rejected transaction
        if isinstance(txid, str):
            if txid == 'txn' or 'error' in txid.lower():
                print(f"{Fore.RED}[{datetime.now()}] Transaction declined from SolanaTracker API for token {token_name}. Response: {txid}{Style.RESET_ALL}")
                await log_buy_sell_error(f"Transaction declined from SolanaTracker API for token {token_name}. Response: {txid}")
                return
        else:
            print(f"{Fore.RED}[{datetime.now()}] Unexpected txid type: {type(txid)}. Response: {txid}{Style.RESET_ALL}")
            await log_buy_sell_error(f"Unexpected txid type for {token_name}. Response: {txid}")
            return

        swap_duration = datetime.now() - swap_start_time
        print(f"{Fore.CYAN}[{datetime.now()}] Transaction initiated: {txid}{Style.RESET_ALL}")

        if txid in processed_transactions:
            print(f"{Fore.YELLOW}[{datetime.now()}] Transaction {txid} has already been processed.{Style.RESET_ALL}")
            return
        processed_transactions.add(txid)

        success = await verify_transaction_status(txid)
        if not success:
            print(f"{Fore.RED}[{datetime.now()}] Buy transaction failed. Skipping further actions.{Style.RESET_ALL}")
            await log_buy_sell_error(f"Buy transaction {txid} failed for {token_name}.")
            return  # Exit if buy transaction fails

        # **Start of Balance Verification with Retries**
        actual_balance = await check_token_balance_with_retries(token_name, max_retries=15, delay=2)
        if actual_balance <= 0:
            print(f"{Fore.RED}[{datetime.now()}] No tokens received after buy transaction.{Style.RESET_ALL}")
            await log_buy_sell_error(f"No tokens received after buy transaction for {token_name}.")
            return
        # **End of Balance Verification**

        # Add contract address to file
        add_contract_to_file(token_name)

        # Increment trade count
        global trade_count
        trade_count += 1

        # Send buy success webhook
        embed = DiscordEmbed(title="Purchase Successful!", description=f"Token: {token_name}", color=0x00FF00)
        embed.add_embed_field(name="Amount", value=f"{buy_amount} SOL")
        embed.add_embed_field(name="Swap Duration", value=f"{swap_duration}")
        embed.add_embed_field(name="Transaction", value=f"[View on Solscan](https://solscan.io/tx/{txid})")
        embed.add_embed_field(name="User", value=USER_NAME)
        await send_discord_webhook(embed, BUY_WEBHOOK_URL)

        # Update received coins via RPC
        received_coins_response, buy_price, fees = await log_and_return_received_coins(swap_response)

        # **Use Verified Token Balance Instead of Response Amount**
        verified_balance = await get_token_balance(token_name)
        if verified_balance != received_coins_response:
            print(f"{Fore.RED}[{datetime.now()}] Discrepancy detected! Expected tokens: {received_coins_response}, Verified tokens: {verified_balance}{Style.RESET_ALL}")
            received_coins = verified_balance  # Use the verified balance
        else:
            received_coins = received_coins_response  # Use the response amount if it matches

        await monitor_token_price(token_name, received_coins, sell_profit, sell_loss, buy_amount, PRIO_FEE)  # Add priority fee
    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception during handle_token_swap: {e}{Style.RESET_ALL}")
        await log_buy_sell_error(f"Exception during handle_token_swap for {token_name}: {e}")



# Function to send wallet balance to webhook
async def send_wallet_balance_webhook():
    
    balance = await check_wallet_balance()

    ctypes.windll.kernel32.SetConsoleTitleW("InsidersOnly | TelegramSniper | User: " + USER_NAME + f" | Balance: {str(balance)} SOL")

    webhook = DiscordWebhook(url=SESSION_START_WEBHOOK_URL)
    embed = DiscordEmbed(title="Wallet Balance Update (CurrentSol)", description=f"Current Balance: {balance} SOL", color=0x0000FF)
    embed.add_embed_field(name="Initial Balance", value=f"{initial_balance} SOL")
    embed.add_embed_field(name="Total Trades", value=f"{trade_count}")
    embed.add_embed_field(name="Current Balance", value=f"{balance} SOL")
    embed.add_embed_field(name="User", value=USER_NAME)
    webhook.add_embed(embed)
    try:
        response = await asyncio.to_thread(webhook.execute)  # Use asyncio.to_thread to run blocking code in separate thread
        if response.status_code != 200:
            print(f"{Fore.RED}[{datetime.now()}] Error sending Discord notification: {response.status_code}, {response.text}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception while sending Discord webhook: {e}{Style.RESET_ALL}")


# Function to send Discord Webhook
async def send_discord_webhook(embed, webhook_url):
    webhook = DiscordWebhook(url=webhook_url)
    webhook.add_embed(embed)
    try:
        response = await asyncio.to_thread(webhook.execute)  # Use asyncio.to_thread to run blocking code in separate thread
        if response.status_code != 200:
            print(f"{Fore.RED}[{datetime.now()}] Error sending Discord notification: {response.status_code} - {response.text}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}[{datetime.now()}] Exception while sending Discord webhook: {e}{Style.RESET_ALL}")


# Function to log buy and sell errors and send to error webhook
async def log_buy_sell_error(message):
    embed = DiscordEmbed(title="Info Notification", description=message, color=0xFF0000)
    await send_discord_webhook(embed, ERROR_WEBHOOK_URL)



# Main Function
async def main():
    global initial_balance, session, current_balance
    # Initialize the aiohttp session
    session = aiohttp.ClientSession()

    try:
        # Check and set initial wallet balance
        balance = await check_wallet_balance()
        initial_balance = balance
        current_balance = balance

        # Send session start webhook to Discord
        embed = DiscordEmbed(title="Session Started", description=f"Current Balance: {initial_balance} SOL", color=0x00FF00)
        embed.add_embed_field(name="Start Time", value=f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        embed.add_embed_field(name="Monitored Groups", value=", ".join([group["group_name"] for group in groups_config]))
        embed.add_embed_field(name="User", value=USER_NAME)
        await send_discord_webhook(embed, SESSION_START_WEBHOOK_URL)

        # Initialize multiple Telegram clients with optimized connection settings
        clients = []
        for client_config in TELEGRAM_CLIENTS:
            if client_config.get("enabled", False):
                client = TelegramClient(
                    client_config["session_name"],
                    client_config["api_id"],
                    client_config["api_hash"],
                    connection=connection.ConnectionTcpAbridged,  # Optimized connection
                    connection_retries=None,                       # Number of retry attempts
                    timeout=3                                       # Timeout for network operations
                )
                clients.append(client)

        if not clients:
            print(f"{Fore.RED}[{datetime.now()}] No Telegram clients are enabled. Please enable at least one client in settings.json.{Style.RESET_ALL}")
            await log_buy_sell_error("No Telegram clients are enabled. Please enable at least one client in settings.json.")
            await session.close()
            exit(1)

        # Define the connect_client function within the main function
        async def connect_client(client, phone_number):
            print(f"{Fore.YELLOW}[{datetime.now()}] Connecting to Telegram (Session: {client.session.filename})...{Style.RESET_ALL}")
            await client.connect()

            if not await client.is_user_authorized():
                print(f"{Fore.RED}[{datetime.now()}] Client {client.session.filename} not authorized! Please log in.{Style.RESET_ALL}")
                await client.send_code_request(phone_number)
                try:
                    # Use asyncio.to_thread for input to avoid blocking the event loop
                    code = await asyncio.to_thread(input, f"{Fore.CYAN}[{datetime.now()}] Enter the code for {phone_number}: {Style.RESET_ALL}")
                    await client.sign_in(phone_number, code)
                except Exception as e:
                    print(f"{Fore.RED}[{datetime.now()}] Login error for {phone_number}: {e}{Style.RESET_ALL}")
                    await log_buy_sell_error(f"Login error for {phone_number}: {e}")
                    await session.close()
                    exit(1)

        # Prepare phone numbers for all clients
        phone_numbers = [client_config["phone_number"] for client_config in TELEGRAM_CLIENTS if client_config.get("enabled", False)]

        # Connect and authorize all clients with dynamic wait time for all except the last
        for index, (client, phone_number) in enumerate(zip(clients, phone_numbers)):
            await connect_client(client, phone_number)
            if index < len(clients) - 1:
                print(f"{Fore.YELLOW}[{datetime.now()}] Connected to client {client.session.filename}. Waiting before connecting the next client...{Style.RESET_ALL}")
                await asyncio.sleep(20)

        # Define a common event handler for new messages
        async def new_message_listener(event):
            await handle_message(event)

        # Register the event handler for all clients
        for client in clients:
            client.add_event_handler(new_message_listener, events.NewMessage)

        print(f"{Fore.GREEN}[{datetime.now()}] Telegram sniper running with {len(clients)} clients...{Style.RESET_ALL}")

        # Run all clients until they are disconnected
        await asyncio.gather(*[client.run_until_disconnected() for client in clients])

    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
