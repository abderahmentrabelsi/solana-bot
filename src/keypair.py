import base58

from loguru import logger
from solders.transaction import Transaction as SolanaTransaction
from solders.keypair import Keypair as SolanaKeypairPySolders
from solders.pubkey import Pubkey
from .env import SECRET_KEY_B58


class SolanaKeypair:
    def __init__(self) -> None:
        try:
            decoded = base58.b58decode(SECRET_KEY_B58)
            if len(decoded) != 64:
                raise ValueError("Decoded key must be 64 bytes (32 secret + 32 public).")
            self._keypair = SolanaKeypairPySolders.from_bytes(decoded)
            logger.info("[SolanaKeypair] Loaded keypair from environment.")
        except Exception as e:
            logger.error(f"[SolanaKeypair] Error loading SECRET_KEY_B58: {e}")
            raise

        self.public_key: Pubkey = self._keypair.pubkey()
        self.secret_key: bytes = self._keypair.to_bytes()

    def sign(self, message: bytes) -> bytes:
        try:
            return self._keypair.sign_message(message)
        except Exception as e:
            logger.error(f"[SolanaKeypair] Signing failed: {e}")
            raise