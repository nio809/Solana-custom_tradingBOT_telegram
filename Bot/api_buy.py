from moralis import sol_api
import os
import base58
import base64
import json
from solders import message
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.types import TxOpts
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from jupiter_python_sdk.jupiter import Jupiter
import asyncio
from moralis import sol_api
import sys
import base58
import base64
import json
from solders import message
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from jupiter_python_sdk.jupiter import Jupiter
import asyncio

# Extract arguments from command line
wallet_address, private_key_str, amount_str = sys.argv[1], sys.argv[2], sys.argv[3]
amount_to_swap = float(amount_str)

api_key = "_____moralis_api_____"
params = {
    "network": "mainnet",
    "address": wallet_address
}

result = sol_api.account.get_portfolio(api_key=api_key, params=params)


# Load private key and initialize client and Jupiter SDK
private_key = Keypair.from_bytes(base58.b58decode(private_key_str))
async_client = AsyncClient("https://blue-dimensional-season.solana-mainnet.quiknode.pro/06d74bfa221b70693a6b57fc958a49b6d521fc29/")


jupiter = Jupiter(
    async_client=async_client,
    keypair=private_key,
    quote_api_url="https://quote-api.jup.ag/v6/quote?",
    swap_api_url="https://quote-api.jup.ag/v6/swap",
)

async def dynamic_slippage(amount, input_mint, output_mint):
    base_slippage = 0.5
    dynamic_slippage = base_slippage + (amount / 1_000_000) * 0.1
    final_slippage_bps = min(50, dynamic_slippage) * 100
    return int(final_slippage_bps)

async def execute_swap():
    input_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" #solana
    output_mint = "So11111111111111111111111111111111111111112" #usdc
    slippage_bps = await dynamic_slippage(amount_to_swap * 1_000_000_000, input_mint, output_mint)
    transaction_data = await jupiter.swap(
        input_mint=input_mint,
        output_mint=output_mint,
        amount=int(amount_to_swap * 1_000_000 ),
        slippage_bps=slippage_bps,
    )
    raw_transaction = VersionedTransaction.from_bytes(base64.b64decode(transaction_data))
    signature = private_key.sign_message(message.to_bytes_versioned(raw_transaction.message))
    signed_txn = VersionedTransaction.populate(raw_transaction.message, [signature])
    opts = TxOpts(skip_preflight=False, preflight_commitment=Processed)
    result = await async_client.send_raw_transaction(txn=bytes(signed_txn), opts=opts)
    transaction_id = json.loads(result.to_json())['result']
    print(f"Transaction sent: https://explorer.solana.com/tx/{transaction_id}")

# Run the async function
asyncio.run(execute_swap())
