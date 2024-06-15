
import sqlite3
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from solders.keypair import Keypair
import base58
from moralis import sol_api
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import time
api_key = "___moralis_api"

session = {}

# Initialize or connect to the database
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# Create the table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    ''' + ', '.join([f'wallet{i+1} TEXT, privatekey{i+1} TEXT' for i in range(150)]) + ')')
conn.commit()

# Initialize the bot
app = Client("my_bot", api_id='_____', api_hash='__________', bot_token='___________')

@app.on_message(filters.command("start"))
def start(client, message):
    keyboard = [
        [InlineKeyboardButton("Wallet", callback_data="wallet")],
        [InlineKeyboardButton("Buy-sell", callback_data="buy_sell")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message.reply_text("Choose an option:", reply_markup=reply_markup)


def get_sol_price():

    params = {
        "network": "mainnet",
        "address": "So11111111111111111111111111111111111111112"
    }
    try:
        result = sol_api.token.get_token_price(api_key=api_key, params=params)
        sol_price = result.get('usdPrice', 'N/A')
        return sol_price
    except Exception as exc:
        print(f"Error fetching SOL price: {exc}")
        return 'N/A'

def fetch_wallet_balances(wallet_address):
    params = {
        "network": "mainnet",
        "address": wallet_address
    }
    result = sol_api.account.get_portfolio(api_key=api_key, params=params)
    usdc_balance = "0"
    sol_balance = "0"
    if 'tokens' in result:
        for token in result['tokens']:
            if token['symbol'] == 'USDC':
                usdc_balance = token['amount']  # This should correctly get '1.358574' from your example
    if 'nativeBalance' in result:
        sol_balance = result['nativeBalance']['solana']
    return wallet_address, usdc_balance, sol_balance

def fetch_all_wallet_balances(wallets):
    balances = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_wallet = {executor.submit(fetch_wallet_balances, wallet): wallet for wallet in wallets}
        for future in as_completed(future_to_wallet):
            wallet_address = future_to_wallet[future]
            try:
                wallet_address, usdc_balance, sol_balance = future.result()
                balances[wallet_address] = (usdc_balance, sol_balance)
            except Exception as exc:
                print(f'{wallet_address} generated an exception: {exc}')
    return balances

@app.on_callback_query()
def handle_callbacks(client, callback_query):
    data = callback_query.data

    if data == "wallet":
        keyboard = [
            [InlineKeyboardButton("Check Wallets", callback_data="wallet_check")],
            [InlineKeyboardButton("Create 1 Wallet", callback_data="create_1")],
            [InlineKeyboardButton("create 10 Wallets", callback_data="create_10")],
            [InlineKeyboardButton("Back", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text("Wallet options:", reply_markup=reply_markup)

    elif data == "buy_sell":
        keyboard = [
            [InlineKeyboardButton("Buy", callback_data="buy")],
            [InlineKeyboardButton("Sell", callback_data="sell_wallets")],
            [InlineKeyboardButton("Back", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text("Buy or Sell:", reply_markup=reply_markup)

    elif data == "sell_wallets":
      sol_price = get_sol_price()
      cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
      user_data = cursor.fetchone()
      total_usdc = 0  # Initialize total USDC balance

      if user_data:
        wallet_addresses = [user_data[2 * i] for i in range(1, 151) if user_data[2 * i] is not None]
        wallet_balances = fetch_all_wallet_balances(wallet_addresses)

        keyboard = []
        for i, wallet_address in enumerate(wallet_addresses, start=1):
            usdc_balance, sol_balance = wallet_balances.get(wallet_address, ("N/A", "N/A"))
            if float(sol_balance) > 0:
                total_usdc += float(sol_balance)  # Sum up USDC balances
                wallet_key_display = f"Wallet{i} ({wallet_address[-5:]}) | USDC {usdc_balance} | Sol {sol_balance}"
                keyboard.append([InlineKeyboardButton(wallet_key_display, callback_data=f"select_percent_{i}")])

        keyboard.append([InlineKeyboardButton("All Wallets | Total Sol: ${:.4f}".format(total_usdc), callback_data="buy_all_wallets")])
        keyboard.append([InlineKeyboardButton("Back", callback_data="buy_sell")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text(f"Select a wallet to buy for: \nCurrent Sol Price: ${sol_price}", reply_markup=reply_markup)
      else:
        callback_query.message.edit_text("No wallets found.")


    elif data.startswith("select_percent_"):
        index = int(data.split('_')[-1])
        keyboard = [
            [InlineKeyboardButton("10%", callback_data=f"sell_10_{index}"), InlineKeyboardButton("25%", callback_data=f"sell_25_{index}")],
            [InlineKeyboardButton("50%", callback_data=f"sell_50_{index}"), InlineKeyboardButton("75%", callback_data=f"sell_75_{index}")],
            [InlineKeyboardButton("100%", callback_data=f"sell_100_{index}"), InlineKeyboardButton("Back", callback_data="sell_wallets")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text("Choose the percentage to sell:", reply_markup=reply_markup)







    elif data.startswith("sell_"):
      percent, index = data.split('_')[1], int(data.split('_')[2])
      cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
      user_data = cursor.fetchone()
      wallet_address = user_data[2 * index]
      private_key = user_data[2 * index + 1]

    # Fetch the current balance for the selected wallet
      wallet_address, usdc_balance, sol_balance = fetch_wallet_balances(wallet_address)
      sol_to_sell = (float(sol_balance) * int(percent) / 100)  # Calculate the amount of SOL to sell

    # Calculate the SOL amount to send, which is 2% of the intended sale
      sol_to_send = sol_to_sell * 0.02

    # Decide the amount of SOL to send based on the threshold
      if sol_to_send < 0.00095:
        sol_to_send = 0.00095  # Ensure at least 0.00095 SOL is sent

    # Send the determined SOL amount without delay
      send_result = subprocess.run(
        ['node', 'sendsol.js', private_key, str(sol_to_send)],
        capture_output=True, text=True
    )
      if send_result.returncode == 0:
        print(f"SOL sent successfully ({sol_to_send:.5f} SOL). Transaction details: {send_result.stdout}")
        time.sleep(1)
        # Proceed to sell the remaining SOL after sending
        remaining_sol_to_sell = sol_to_sell - sol_to_send
        if remaining_sol_to_sell > 0:
            sell_result = subprocess.run(
                ['python3', 'api_sell.py', wallet_address, private_key, str(remaining_sol_to_sell)],
                capture_output=True, text=True
            )
            if sell_result.returncode == 0:
                output = sell_result.stdout
                start_index = output.find("Transaction sent:")
                if start_index != -1:
                    start_index += len("Transaction sent:")
                    transaction_link = output[start_index:].strip()
                    response = f"Selling {remaining_sol_to_sell:.5f} SOL from Wallet {index}.\nTransaction Link: {transaction_link}"
                else:
                    response = "Transaction link not found."
            else:
                response = f"Error during transaction: {sell_result.stderr}"
        else:
            response = "No remaining SOL to sell after transfer."
      else:
        print(f"Failed to send SOL. Error: {send_result.stderr}")
        response = "Failed to send SOL. Cannot proceed with sale."

    # Adding a Back button to the response
      keyboard = [[InlineKeyboardButton("Back", callback_data="sell_wallets")]]
      reply_markup = InlineKeyboardMarkup(keyboard)
      callback_query.message.edit_text(response, reply_markup=reply_markup)









    elif data == "buy_all_wallets":
      sol_price = get_sol_price()
      cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
      user_data = cursor.fetchone()
      total_usdc = 0  # Initialize total USDC balance

      non_empty_wallets = {}  # Dictionary to store non-empty wallets and private keys

      if user_data:
        # Retrieving wallet addresses and corresponding private keys if they are not None
        wallet_addresses = [(user_data[2*i], user_data[2*i+1]) for i in range(1, 151) if user_data[2*i] is not None]
        wallet_balances = fetch_all_wallet_balances([addr[0] for addr in wallet_addresses])

        for i, (wallet_address, private_key) in enumerate(wallet_addresses, start=1):
            usdc_balance, sol_balance = wallet_balances.get(wallet_address, ("N/A", "N/A"))
            if float(usdc_balance) > 0:
                total_usdc += float(usdc_balance)  # Sum up USDC balances
                # Store wallet address and private key if USDC balance is non-zero
                non_empty_wallets[wallet_address] = private_key
            else:
             callback_query.message.edit_text("No wallets with balance")

        session['non_empty_wallets'] = non_empty_wallets

        usdc_to_spend = total_usdc 
        sol_to_buy = usdc_to_spend / float(sol_price)

        keyboard = [
            [InlineKeyboardButton(f"{sol_to_buy * 0.1:.4f} ", callback_data=f"buy_sol_{sol_to_buy * 0.1}")],
            [InlineKeyboardButton(f"{sol_to_buy * 0.25:.4f} ", callback_data=f"buy_sol_{sol_to_buy * 0.25}")],
            [InlineKeyboardButton(f"{sol_to_buy * 0.5:.4f} ", callback_data=f"buy_sol_{sol_to_buy * 0.5}")],
            [InlineKeyboardButton(f"{sol_to_buy * 0.75:.4f} ", callback_data=f"buy_sol_{sol_to_buy * 0.75}")],
            [InlineKeyboardButton(f"{sol_to_buy:.4f} SOL (100%)", callback_data=f"buy_sol_{sol_to_buy}")],
            [InlineKeyboardButton("Back", callback_data="buy")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text(f"You can randomly buy up to {sol_to_buy:.4f} \n Choose an option:", reply_markup=reply_markup)
      else:
        callback_query.message.edit_text("No wallets found.")

    
    
    elif data.startswith("buy_sol_"):
      sol_amount = float(data.split('_')[-1])
      sol_price = get_sol_price()  # Fetch the current SOL price
      total_usdc_needed = sol_amount * sol_price

    # Retrieve the stored non-empty wallets from the session
      non_empty_wallets = session.get('non_empty_wallets', {})

    # Get balances and calculate proportional contributions
      wallet_balances = {wallet: float(fetch_wallet_balances(wallet)[1]) for wallet in non_empty_wallets.keys()}
      total_available_usdc = sum(wallet_balances.values())

      contributions = {}
      if total_available_usdc >= total_usdc_needed:
        # Calculate proportional contributions based on total_usdc_needed
        for wallet_address, balance in wallet_balances.items():
            contribution = (balance / total_available_usdc) * total_usdc_needed
            contributions[wallet_address] = contribution
            total_usdc_needed -= contribution

        # Execute buying process in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for wallet_address, contribution in contributions.items():
                private_key = non_empty_wallets[wallet_address]
                # Launch the buying process via an external script
                futures.append(executor.submit(subprocess.run, ['python3', 'api_buy.py', wallet_address, private_key, str(contribution)],
                                               capture_output=True, text=True))

            # Collect results
            transaction_links = []
            for future in futures:
                result = future.result()
                if result.returncode == 0:
                    output = result.stdout
                    transaction_links.append(output.strip())  # Assume output is a direct link or message
                else:
                    print(f"Error during transaction: {result.stderr}")

        # Build the response with transaction links
        response = "Transactions completed successfully:\n"
        for link in transaction_links:
            response += f"Transaction Link: {link}\n"
      else:
        response = "Insufficient total USDC across all wallets to perform this purchase."
        # Skip further processing and show error message

    # Add a back button to return to previous options
      keyboard = [[InlineKeyboardButton("Back", callback_data="start")]]
      reply_markup = InlineKeyboardMarkup(keyboard)

    # Edit the message on the Telegram client to show the transaction results
      callback_query.message.edit_text(response, reply_markup=reply_markup)


    
    
    
    
    elif data == "buy":
      sol_price = get_sol_price()
      cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
      user_data = cursor.fetchone()
      total_usdc = 0  # Initialize total USDC balance

      if user_data:
        wallet_addresses = [user_data[2 * i] for i in range(1, 151) if user_data[2 * i] is not None]
        wallet_balances = fetch_all_wallet_balances(wallet_addresses)

        keyboard = []
        for i, wallet_address in enumerate(wallet_addresses, start=1):
            usdc_balance, sol_balance = wallet_balances.get(wallet_address, ("N/A", "N/A"))
            if float(usdc_balance) > 0:
                total_usdc += float(usdc_balance)  # Sum up USDC balances
                wallet_key_display = f"Wallet{i} ({wallet_address[-5:]}) | USDC {usdc_balance} | Sol {sol_balance}"
                keyboard.append([InlineKeyboardButton(wallet_key_display, callback_data=f"select_buy_percent_{i}")])

        keyboard.append([InlineKeyboardButton("All Wallets | Total USDC: ${:.2f}".format(total_usdc), callback_data="buy_all_wallets")])
        keyboard.append([InlineKeyboardButton("Back", callback_data="buy_sell")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text(f"Select a wallet to buy for: \nCurrent Sol Price: ${sol_price}", reply_markup=reply_markup)
      else:
        callback_query.message.edit_text("No wallets found.")


    elif data.startswith("select_buy_percent_"):
        index = int(data.split('_')[-1])
        keyboard = [
            [InlineKeyboardButton("10%", callback_data=f"buy_10_{index}"), InlineKeyboardButton("25%", callback_data=f"buy_25_{index}")],
            [InlineKeyboardButton("50%", callback_data=f"buy_50_{index}"), InlineKeyboardButton("75%", callback_data=f"buy_75_{index}")],
            [InlineKeyboardButton("100%", callback_data=f"buy_100_{index}"), InlineKeyboardButton("Back", callback_data="buy")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text("Choose the percentage of your USDC balance to spend:", reply_markup=reply_markup)


    elif data.startswith("buy_"):
      percent, index = data.split('_')[1], int(data.split('_')[2])
      cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
      user_data = cursor.fetchone()
      wallet_address = user_data[2 * index]
      private_key = user_data[2 * index + 1]

    # Fetch the current USDC balance for the selected wallet
      wallet_address, usdc_balance, sol_balance = fetch_wallet_balances(wallet_address)

      usdc_to_spend = (float(usdc_balance) * int(percent) / 100)

    # Check if the calculated amount to spend is within acceptable limits
      if usdc_to_spend < 1:  # Assuming USD 1 is the minimum transaction threshold
        response = f"Error: The amount of USDC to spend is too low (${usdc_to_spend:.2f}). Please choose a higher percentage."
      else:
        # Call the external script to perform the purchase
        result = subprocess.run(
            ['python3', 'api_buy.py', wallet_address, private_key, str(usdc_to_spend)],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            # Extract the transaction link
            output = result.stdout
            start_index = output.find("Transaction sent:")
            if start_index != -1:
                start_index += len("Transaction sent:")
                transaction_link = output[start_index:].strip()
                response = f"Bought USD {usdc_to_spend:.2f} worth of SOL in Wallet {index}.\nTransaction Link: {transaction_link}"

                # Fetch current SOL price to calculate the value of 2% SOL
                sol_price = get_sol_price()
                # Calculate the SOL amount that represents 2% of the USDC spent
                sol_to_send = (usdc_to_spend * 0.02) / float(sol_price)

                # Check if the calculated SOL to send is less than the threshold
                if sol_to_send < 0.00095:
                    sol_to_send = 0.00095  # Send the minimum threshold amount if calculated less

                # Wait for 50 seconds before sending SOL
                time.sleep(30)
                
                
                send_result = subprocess.run(
                    ['node', 'sendsol.js', private_key, str(sol_to_send)],
                    capture_output=True, text=True
                )
                if send_result.returncode == 0:
                    print(f"SOL sent successfully ({sol_to_send:.5f} SOL). Transaction details: {send_result.stdout}")
                else:
                    print(f"Failed to send SOL. Error: {send_result.stderr}")
            else:
                response = "Transaction link not found."
        else:
            response = f"Error during transaction: {result.stderr}"

    # Adding a Back button to the response
      keyboard = [[InlineKeyboardButton("Back", callback_data="buy")]]
      reply_markup = InlineKeyboardMarkup(keyboard)
      callback_query.message.edit_text(response, reply_markup=reply_markup)



    elif data == "start":
        start(client, callback_query.message)
    elif data in ["create_1", "create_10"]:
        create_wallets(client, callback_query, data)
    
 
    


    elif data == "wallet_check":
      cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
      user_data = cursor.fetchone()

      if user_data:
        wallet_addresses = [user_data[2*i] for i in range(1, 151) if user_data[2*i] is not None]
        wallet_balances = fetch_all_wallet_balances(wallet_addresses)
        keyboard = []
        for i, wallet in enumerate(wallet_addresses, start=1):
            usdc_balance, sol_balance = wallet_balances.get(wallet, ("N/A", "N/A"))
            wallet_key_display = f"Wallet{i} ({wallet[-5:]}) | USDC {usdc_balance} | Sol {sol_balance}"
            keyboard.append([InlineKeyboardButton(wallet_key_display, callback_data=f"wallet_details_{i}")])

        # Add the Back button after listing all the wallets
        keyboard.append([InlineKeyboardButton("Back", callback_data="start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        callback_query.message.edit_text("Your wallets:", reply_markup=reply_markup)
      else:
        callback_query.message.edit_text("No wallets found.")

    elif data.startswith("wallet_details_"):
        index = int(data.split('_')[-1])
        cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
        user_data = cursor.fetchone()
        wallet = user_data[2 * index]
        if wallet:
            response = f"Full Wallet Address: {wallet}\n"
            keyboard = [[InlineKeyboardButton("Back", callback_data="wallet_check")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            callback_query.message.edit_text(response, reply_markup=reply_markup)


            
def create_wallets(client, callback_query, data):
    num_wallets = 1 if data == 'create_1' else 10
    cursor.execute('SELECT * FROM users WHERE chat_id=?', (callback_query.from_user.id,))
    user_data = cursor.fetchone()

    if user_data is None:
        cursor.execute('INSERT INTO users (chat_id, username) VALUES (?, ?)', (callback_query.from_user.id, callback_query.from_user.username))
        conn.commit()
        user_data = [callback_query.from_user.id, callback_query.from_user.username] + [None] * 300

    next_available_index = next((i for i in range(1, 151) if user_data[1 + 2 * i] is None), 151)

    if next_available_index > 150:
        callback_query.message.edit_text("You have reached the maximum number of wallets.")
        return

    response = ""
    for _ in range(num_wallets):
        keypair = Keypair()
        secret_key_bytes = bytes(keypair)
        public_key_bytes = bytes(keypair.pubkey())
        encoded_secret_key = base58.b58encode(secret_key_bytes).decode('utf-8')
        encoded_public_key = base58.b58encode(public_key_bytes).decode('utf-8')

        cursor.execute(f'UPDATE users SET wallet{next_available_index}=?, privatekey{next_available_index}=? WHERE chat_id=?',
                       (encoded_public_key, encoded_secret_key, callback_query.from_user.id))
        conn.commit()
        response += f"Wallet ID: {encoded_public_key}\nPrivate Key: {encoded_secret_key}\n\n"
        next_available_index += 1

    keyboard = [[InlineKeyboardButton("Back", callback_data="wallet")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    callback_query.message.edit_text(response, reply_markup=reply_markup)


if __name__ == "__main__":
    app.run()  # Start the bot .