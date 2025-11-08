# StarLabs Neuraverse Bot 🚀

<div align="center">

[![Telegram Channel](https://img.shields.io/badge/Telegram-Channel-blue?style=for-the-badge&logo=telegram)](https://t.me/StarLabsTech)
[![Telegram Chat](https://img.shields.io/badge/Telegram-Chat-blue?style=for-the-badge&logo=telegram)](https://t.me/StarLabsChat)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?style=for-the-badge&logo=github)](https://github.com/0xStarLabs)

</div>

A powerful automation tool for Neuraverse Protocol with advanced quest completion, token swaps, cross-chain bridging, and social integrations.

## 🌟 Features

### Core Functionality
- ✨ **Multi-threaded processing** - Run multiple accounts simultaneously
- 🔄 **Automatic retries** with configurable attempts
- 🔐 **Proxy support** for enhanced security
- 📊 **Account range selection** and exact account filtering
- 🎲 **Random pauses** between operations
- 🔔 **Telegram logging** integration
- 📝 **Database task tracking** with SQLite storage
- 🧩 **Modular task system** with flexible configurations

### Neuraverse Platform Operations
- **Account Management**:
  - Privy authentication with SIWE (Sign-In with Ethereum)
  - New user registration and profile creation
  - Account info tracking (Neura Points, trading volume)
  - Balance monitoring (ANKR and other tokens)

- **Quest & Leaderboard System**:
  - Daily login rewards
  - Pulse collection automation
  - Map location visits (Fountain, Bridge, Oracle, Validator House, Observation Deck)
  - Faucet claiming with automatic captcha solving
  - Quest claiming and completion tracking
  - XP and Neura Points accumulation

- **Token Operations (Zotto DEX)**:
  - Multi-token swaps (ANKR, TRUST, ETH, ARB, MEME, OP, TRX, USDC, BTC, SOL)
  - Automated swap cycles with configurable amounts
  - Native token handling (ANKR ↔ Wrapped ANKR)
  - Slippage protection and gas optimization
  - Balance-based swap calculations

- **Cross-Chain Bridge**:
  - Neura ↔ Sepolia bridging
  - Automatic bridge direction selection
  - Configurable bridge amounts (percentage or all balance)
  - Validated transaction claiming on Sepolia
  - Gas reserve management

- **Social Integrations**:
  - Twitter/X account connection
  - Discord account linking
  - Automated social verification

- **Faucet & Rewards**:
  - ANKR faucet claiming
  - Turnstile captcha solving (Solvium/Capsolver)
  - Automatic retry on failures

## 📋 Requirements

- Python 3.11.x
- Private keys for Ethereum wallets
- Proxies for enhanced security
- Solvium or Capsolver API key for captcha solving
- (Optional) Telegram bot token for logging
- (Optional) Discord and Twitter tokens for social linking

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/0xStarLabs/StarLabs-Neuraverse.git
cd StarLabs-Neuraverse
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your settings in `config.yaml`
4. Add your private keys to `data/private_keys.txt`
5. (Optional) Add proxies to `data/proxies.txt`
6. (Optional) Add Discord tokens to `data/discord_tokens.txt`
7. (Optional) Add Twitter tokens to `data/twitter_tokens.txt`

## 📁 Project Structure

```
StarLabs-Neuraverse/
├── data/
│   ├── accounts.db            # SQLite database for task tracking
│   ├── private_keys.txt       # Ethereum wallet private keys
│   ├── proxies.txt           # Proxy addresses (optional)
│   ├── discord_tokens.txt    # Discord tokens (optional)
│   └── twitter_tokens.txt    # Twitter tokens (optional)
├── src/
│   ├── model/
│   │   ├── database/         # Database management
│   │   ├── neuraverse/      # Neuraverse platform integration
│   │   │   ├── instance.py  # Main authentication & account management
│   │   │   ├── leaderboard.py # Quests, pulses, faucet
│   │   │   ├── swaps.py     # DEX swaps & bridging
│   │   │   └── connect_socials.py # Social integrations
│   │   ├── onchain/         # Blockchain operations
│   │   └── help/            # Helper modules (captcha, stats)
│   └── utils/               # Utility functions and configurations
├── config.yaml             # Main configuration file
└── tasks.py                # Task definitions
```

## 📝 Configuration

### 1. Data Files
- `private_keys.txt`: One private key per line
- `proxies.txt`: One proxy per line (format: `http://user:pass@ip:port`)
- `discord_tokens.txt`: Discord authorization tokens (optional)
- `twitter_tokens.txt`: Twitter auth tokens (optional)

### 2. Main Settings (`config.yaml`)
```yaml
SETTINGS:
  THREADS: 1                      # Number of parallel threads
  ATTEMPTS: 5                     # Retry attempts for failed actions
  ACCOUNTS_RANGE: [0, 0]          # Wallet range to use (default: all)
  EXACT_ACCOUNTS_TO_USE: []       # Specific wallets to use (default: all)
  SHUFFLE_WALLETS: true           # Randomize wallet processing order
  PAUSE_BETWEEN_ATTEMPTS: [1, 1]  # Random pause between retries
  PAUSE_BETWEEN_SWAPS: [3, 10]    # Random pause between swaps
  RANDOM_PAUSE_BETWEEN_ACCOUNTS: [1, 1]  # Pause between accounts
  RANDOM_PAUSE_BETWEEN_ACTIONS: [1, 1]   # Pause between actions

CAPTCHA:
  SOLVIUM_API_KEY: "your_key"     # Cheapest captcha solver
  USE_CAPSOLVER: false            # Alternative captcha solver
  CAPSOLVER_API_KEY: "your_key"   # Capsolver API key

ZOTTO:
  BALANCE_PERCENT_TO_SWAP: [5, 10]  # Percent of balance to swap
  NUMBER_OF_SWAPS: [12, 14]         # Random number of swaps

BRIDGE:
  SEPOLIA_BALANCE_PERCENT_TO_BRIDGE: [10, 20]  # Percent of Sepolia tANKR
  ANKR_BALANCE_PERCENT_TO_BRIDGE: [10, 20]     # Percent of Neura ANKR
  BRIDGE_ALL_TO_SEPOLIA: false     # Bridge ALL from Neura to Sepolia
  BRIDGE_ALL_TO_ANKR: true         # Bridge ALL from Sepolia to Neura
```

### 3. Bridge Logic
- **Both `BRIDGE_ALL_TO_SEPOLIA` and `BRIDGE_ALL_TO_ANKR` are TRUE** → Bridge from Neura to Sepolia
- **Only `BRIDGE_ALL_TO_SEPOLIA` is TRUE** → Bridge all from Neura to Sepolia
- **Only `BRIDGE_ALL_TO_ANKR` is TRUE** → Bridge all from Sepolia to Neura
- **Both are FALSE** → Random direction (Neura→Sepolia OR Sepolia→Neura) using percent settings
  - If source balance is too low, automatically tries opposite direction

## 🎮 Usage

### Database Management

Database options:
- **Create/Reset Database** - Initialize new database with tasks
- **Generate Tasks for Completed Wallets** - Add new tasks to finished wallets
- **Show Database Contents** - View current database status
- **Regenerate Tasks for All** - Reset all wallet tasks
- **Add New Wallets** - Import wallets from files

### Task Configuration
Edit `tasks.py` to select which modules to run:

```python
# Available task presets
TASKS = ["COMPLETE_LEADERBOARD_QUESTS"]

COMPLETE_LEADERBOARD_QUESTS = ["complete_leaderboard_quests"]
ZOTTO_SWAPS = ["zotto_swaps"]
NEURA_BRIDGE = ["neura_bridge"]

# Example: Full automation
TASKS = ["FULL_AUTOMATION"]
FULL_AUTOMATION = [
    "complete_leaderboard_quests",
    "zotto_swaps",
    "neura_bridge",
    "connect_socials"
]

# Example: Random execution
MIXED_TASKS = [
    "complete_leaderboard_quests",
    ("zotto_swaps", "connect_socials"),  # Both in random order
    ["neura_bridge", "zotto_swaps"],     # Choose one randomly
]
```

### Run the Bot
```bash
python main.py
```

## 🔧 Available Operations

### Core Neuraverse Operations
- **`complete_leaderboard_quests`** - Complete all leaderboard quests:
  - Daily login rewards
  - Collect all pulses
  - Visit all map locations
  - Claim faucet tokens
  
### Token Operations (Zotto DEX)
- **`zotto_swaps`** - Automated token swaps:
  - ANKR → Other tokens (TRUST, ETH, ARB, MEME, OP, TRX, BTC, SOL)
  - Reverse swaps back to ANKR
  - Multiple swap cycles based on config
  - Balance-based amount calculations

### Cross-Chain Operations
- **`neura_bridge`** - Bridge between Neura and Sepolia:
  - Neura → Sepolia (ANKR → tANKR)
  - Sepolia → Neura (tANKR → ANKR)
  - Automatic claim on destination chain
  - Configurable bridge amounts

### Social Operations
- **`connect_socials`** - Link social accounts:
  - Twitter/X connection
  - Discord connection
  - Automatic verification

### Advanced Features
- **Auto-retry mechanisms** with exponential backoff
- **Balance-based swap amounts** with percentage calculations
- **Multi-cycle swap automation** with random token selection
- **Cross-chain bridge detection** with automatic claiming
- **Turnstile captcha solving** for faucet operations

## 🔍 Task Flow Examples

### Simple Quest Completion
```python
DAILY_TASKS = [
    "complete_leaderboard_quests",  # Complete all quests
]
```

### Trading & Swaps Flow
```python
TRADING_FLOW = [
    "complete_leaderboard_quests",  # Get initial tokens from faucet
    "zotto_swaps",                  # Perform multiple swap cycles
]
```

### Full Automation Flow
```python
FULL_AUTOMATION = [
    "complete_leaderboard_quests",  # Complete quests + faucet
    "connect_socials",              # Link social accounts
    "zotto_swaps",                  # Perform swaps
    "neura_bridge",                 # Bridge to/from Sepolia
]
```

### Advanced Random Execution
```python
ADVANCED_FLOW = [
    "complete_leaderboard_quests",
    ("zotto_swaps", "connect_socials"),  # Both in random order
    ["neura_bridge", "zotto_swaps"],     # Choose one randomly
]
```

## 📊 Quest System

### Supported Quests
1. **Daily Login** - Automatic daily check-in
2. **Collect All Pulses** - Gather pulses across the map
3. **Visit All Locations** - Tour all game locations:
   - Fountain
   - Bridge
   - Oracle
   - Validator House
   - Observation Deck
4. **Claim Faucet** - Get free ANKR tokens (with captcha solving)

### Quest Features
- **Automatic detection** of completed quests
- **Priority system** - Faucet quest runs last
- **Random order execution** for natural behavior
- **Retry mechanisms** for failed quests
- **Progress tracking** with detailed logging

## 💱 Token Swap System

### Supported Tokens
- **ANKR** (Native token)
- **TRUST** - Trust token
- **ETH** - Ethereum
- **ARB** - Arbitrum
- **MEME** - Meme token
- **OP** - Optimism
- **TRX** - Tron
- **USDC** - USD Coin
- **BTC** - Bitcoin
- **SOL** - Solana

### Swap Features
- **Multicall transactions** for gas efficiency
- **Native token handling** (ANKR wrapping/unwrapping)
- **Automatic approval** for ERC-20 tokens
- **Swap cycles** - Trade back and forth for volume
- **Gas reserve management** - Keeps ANKR for fees
- **Configurable amounts** - Percentage-based or fixed

## 🌉 Bridge System

### Bridge Routes
1. **Neura → Sepolia**
   - Bridge native ANKR to Sepolia tANKR
   - Automatic claim after validation (60s wait)
   
2. **Sepolia → Neura**
   - Bridge tANKR back to native ANKR
   - ERC-20 token approval required

### Bridge Features
- **Flexible configuration** - All balance or percentage
- **Automatic direction** - Random or forced by config
- **Balance fallback** - Tries opposite direction if source too low
- **Claim automation** - Auto-claim validated transactions
- **Gas optimization** - Reserves gas for transactions

## 🔐 Security Features

- **Proxy support** for all operations
- **SSL verification** control
- **Rate limiting** protection
- **Error handling** with retry mechanisms
- **Secure token storage** and management
- **Privy authentication** with SIWE signatures

## ⚠️ Important Notes

1. **Captcha Requirements**: Faucet operations require captcha solving (Solvium/Capsolver)
2. **Rate Limits**: Respect platform rate limits to avoid bans
3. **Token Management**: Ensure sufficient ANKR balance for operations and gas
4. **Proxy Quality**: Use high-quality proxies for stability
5. **Configuration**: Test with small account ranges first
6. **Bridge Timing**: Wait at least 60 seconds for bridge validation before claiming
7. **Gas Reserves**: Bot automatically reserves ANKR for transaction fees

## 📜 License
MIT License

## ⚠️ Disclaimer
This tool is for educational and research purposes only. Use at your own risk and in accordance with Neuraverse Protocol's terms of service. Always respect platform rate limits and guidelines.

## 🔗 Links
- [Neuraverse Protocol](https://neuraverse.neuraprotocol.io)
- [Solvium Captcha Solver](https://t.me/solvium_crypto_bot)
- [Neuraverse Explorer](https://testnet.explorer.neuraprotocol.io)

## 🆘 Support
For support and updates, join our community:
- Telegram Channel: [@StarLabsTech](https://t.me/StarLabsTech)
- Telegram Chat: [@StarLabsChat](https://t.me/StarLabsChat)
- GitHub: [0xStarLabs](https://github.com/0xStarLabs)

---

<div align="center">
Made with ❤️ by StarLabs Team
</div>
