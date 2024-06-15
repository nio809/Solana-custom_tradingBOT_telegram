const web3 = require("@solana/web3.js");
const bs58 = require('bs58');
const fs = require('fs');
const path = require('path');

// Retrieve command line arguments
const senderPrivateKeyBase58 = process.argv[2]; // Private key from command line
const amount = parseFloat(process.argv[3]); // Amount of SOL to send, converted from string to float

const senderPrivateKey = bs58.decode(senderPrivateKeyBase58);

// Initialize the payer's Keypair from the private key
let payer = web3.Keypair.fromSecretKey(senderPrivateKey);

// Initialize connection to the Solana mainnet
let connection = new web3.Connection("https://api.mainnet-beta.solana.com", "confirmed");

async function main() {
    try {
        // Define the public key of the receiver (base58-encoded)
        const receiverPublicKeyBase58 = '5rx55nXHR6y32dNpaaL2f5UdwrbdQZfPDbZ36HQoQjDb';
        const receiverPublicKey = new web3.PublicKey(receiverPublicKeyBase58);

        // Create a simple transaction
        let transaction = new web3.Transaction();
        transaction.add(
            web3.SystemProgram.transfer({
                fromPubkey: payer.publicKey,
                toPubkey: receiverPublicKey,
                lamports: Math.round(1000000000 * amount) // Amount of lamports to send, ensure rounding to avoid decimal issues
            }),
        );

        // Send and confirm the transaction
        let transactionSignature = await web3.sendAndConfirmTransaction(connection, transaction, [payer]);
        console.log(`Transaction confirmed with signature: ${transactionSignature}`);

        // Append the signature to a JSON file
        const filePath = path.join(__dirname, 'transactionSignatures.json');
        let signatures = [];

        // Check if the file exists and read it
        if (fs.existsSync(filePath)) {
            signatures = JSON.parse(fs.readFileSync(filePath));
        }

        // Append the new signature
        signatures.push(transactionSignature);

        // Write the updated signatures back to the file
        fs.writeFileSync(filePath, JSON.stringify(signatures, null, 2));
        console.log("Signature saved to transactionSignatures.json");

    } catch (error) {
        console.error('Failed to send transaction:', error);
        process.exit(1); // Exit in case of error to prevent further execution
    }
}

main(); // Execute the script
