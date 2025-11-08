from typing import Protocol
from primp import AsyncClient
from eth_account import Account

from src.model.onchain.web3_custom import Web3Custom
from src.utils.config import Config


class NeuraverseProtocol(Protocol):
    """Protocol class for Neuraverse type hints to avoid circular imports"""

    account_index: int
    session: AsyncClient
    web3: Web3Custom
    config: Config
    wallet: Account
    discord_token: str
    twitter_token: str
    proxy: str

    privy_session_token: str
    identity_token: str
    privy_refresh_token: str

    async def get_account_info(self) -> dict | None: ...
    async def connect_socials(self) -> bool: ...


SUPPORTED_LEADERBOARD_QUESTS_IDS = [
    "daily_login",
    "collect_all_pulses",
    "visit_all_map",
    "claim_faucet",
]
SUPPORTED_GAME_VISIT_LOCATIONS_IDS = [
    "game:visitFountain",
    "game:visitBridge",
    "game:visitOracle",
    "game:visitValidatorHouse",
    "game:visitObservationDeck",
]

SWAP_ROUTER_ADDRESS = '0x5AeFBA317BAba46EAF98Fd6f381d07673bcA6467'
WANKR_ADDRESS = '0xBd833b6eCC30CAEaBf81dB18BB0f1e00C6997E7a'
BTC_TOKEN_ADDRESS = '0x5e06D1bd47dd726A9bcd637e3D2F86B236e50c26'

# Bridge constants
NEURA_BRIDGE_ADDRESS = '0xc6255a594299F1776de376d0509aB5ab875A6E3E'
SEPOLIA_BRIDGE_ADDRESS = '0xc6255a594299F1776de376d0509aB5ab875A6E3E'
SEPOLIA_TANKR_ADDRESS = '0xB88Ca91Fef0874828e5ea830402e9089aaE0bB7F'
SEPOLIA_RPC = 'https://ethereum-sepolia-rpc.publicnode.com/'
SEPOLIA_CHAIN_ID = 11155111
NEURA_CHAIN_ID = 267

AVAILABLE_TOKENS = [
    {
        "address": "0xBd833b6eCC30CAEaBf81dB18BB0f1e00C6997E7a",
        "symbol": "ANKR",
        "decimals": 18
    },
    {
        "address": "0x193Fa458F8e95fB8A7319F8285533D6a62cD22c9",
        "symbol": "TRUST",
        "decimals": 18
    },
    {
        "address": "0x1ab357522ED5c1A76F361520dec1b02A3eD04014",
        "symbol": "ETH",
        "decimals": 18
    },
    {
        "address": "0x2444fAe99F9Aa127043032BE8589fAC4b601c733",
        "symbol": "ARB",
        "decimals": 18
    },
    {
        "address": "0x3442890133041090786645D610f2F92f092C89B9",
        "symbol": "MEME",
        "decimals": 18
    },
    {
        "address": "0x3630388bd5e6927b7B6F8B6Eb5863315D9401401",
        "symbol": "OP",
        "decimals": 18
    },
    {
        "address": "0x3655CCbd4E10C74E5bb48B016fd88FA468f49324",
        "symbol": "TRX",
        "decimals": 18
    },
    {
        "address": "0x4e050bB4930C60595495f3a1A70bAc6c6c53FCB2",
        "symbol": "USDC",
        "decimals": 18
    },
    {
        "address": "0x5e06D1bd47dd726A9bcd637e3D2F86B236e50c26",
        "symbol": "BTC",
        "decimals": 18
    },
    {
        "address": "0xaFAfc2942Ba7F1C47a9E453Ea1a55bE3c5A55652",
        "symbol": "SOL",
        "decimals": 18
    },
]
SWAP_ROUTER_ABI = [
    {
        "inputs": [{"internalType": "bytes[]", "name": "data", "type": "bytes[]"}],
        "name": "multicall",
        "outputs": [{"internalType": "bytes[]", "name": "results", "type": "bytes[]"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# Bridge ABIs
NEURA_BRIDGE_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "_recipient", "type": "address"},
            {"internalType": "uint256", "name": "_chainId", "type": "uint256"}
        ],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]

SEPOLIA_BRIDGE_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "assets", "type": "uint256"},
            {"internalType": "address", "name": "receiver", "type": "address"}
        ],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

BRIDGE_CLAIM_ABI = [
    {
        "inputs": [
            {"internalType": "bytes", "name": "encodedMessage", "type": "bytes"},
            {"internalType": "bytes[]", "name": "messageSignatures", "type": "bytes[]"}
        ],
        "name": "claim",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]