#!/usr/bin/env python3
import nacl.signing
import base58

def generate_solana_private_key():
    # Generate a new random signing (private) key.
    signing_key = nacl.signing.SigningKey.generate()
    # Concatenate the 32-byte seed with the 32-byte public key
    full_secret = signing_key.encode() + signing_key.verify_key.encode()
    # Encode the 64-byte secret key to a base58 string
    return base58.b58encode(full_secret).decode('utf-8')

def main():
    print("Solana Private Key (Base58):", generate_solana_private_key())
