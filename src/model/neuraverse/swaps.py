import asyncio
import random
import time
from typing import Optional
from loguru import logger
from eth_abi.abi import encode as abi_encode
from web3 import AsyncWeb3

from src.model.neuraverse.constants import (
    NeuraverseProtocol,
    SWAP_ROUTER_ADDRESS,
    WANKR_ADDRESS,
    ERC20_ABI,
    AVAILABLE_TOKENS,
    NEURA_BRIDGE_ADDRESS,
    SEPOLIA_BRIDGE_ADDRESS,
    SEPOLIA_TANKR_ADDRESS,
    SEPOLIA_RPC,
    SEPOLIA_CHAIN_ID,
    NEURA_BRIDGE_ABI,
    SEPOLIA_BRIDGE_ABI,
    BRIDGE_CLAIM_ABI
)
from src.model.onchain.constants import Balance
from src.utils.decorators import retry_async


class NeuraSwaps:
    def __init__(self, neuraverse: NeuraverseProtocol):
        self.neuraverse = neuraverse
        self.account_index = neuraverse.account_index
        self.web3 = neuraverse.web3
        self.wallet = neuraverse.wallet
        self.config = neuraverse.config
        self.available_tokens = []
        self.sepolia_web3 = None

    async def fetch_available_tokens(self) -> Optional[list]:
        try:
            self.available_tokens = AVAILABLE_TOKENS
            return self.available_tokens
            
        except Exception as e:
            logger.error(f"{self.account_index} | Failed to load tokens: {e}")
            return None

    def encode_inner_swap(self, token_in: str, token_out: str, recipient: str, deadline_ms: int, amount_in_wei: int) -> str:
        """Encode inner swap call with function selector 0x1679c792"""
        inner_params = abi_encode(
            ['address', 'address', 'uint256', 'address', 'uint256', 'uint256', 'uint256', 'uint256'],
            [
                self.web3.web3.to_checksum_address(token_in),
                self.web3.web3.to_checksum_address(token_out),
                0,
                self.web3.web3.to_checksum_address(recipient),
                int(deadline_ms),
                int(amount_in_wei),
                27,
                0
            ]
        )
        return '0x1679c792' + inner_params.hex()
    
    def encode_unwrap_weth9(self, amount_minimum: int, recipient: str) -> str:
        """Encode unwrapWETH9 call with function selector 0x49616997"""
        unwrap_params = abi_encode(
            ['uint256', 'address'],
            [int(amount_minimum), self.web3.web3.to_checksum_address(recipient)]
        )
        return '0x49616997' + unwrap_params.hex()

    @retry_async(default_value=None)
    async def get_token_balance(self, token_address: str) -> Optional[Balance]:
        try:
            if token_address.lower() == WANKR_ADDRESS.lower():
                return await self.web3.get_balance(self.wallet.address)
            else:
                return await self.web3.get_token_balance(
                    wallet_address=self.wallet.address,
                    token_address=token_address,
                    token_abi=ERC20_ABI,
                    decimals=18
                )
        except Exception as e:
            logger.error(f"{self.account_index} | Error getting token balance: {e}")
            return None

    @retry_async(default_value=False)
    async def perform_swap(self, token_in: dict, token_out: dict, amount_in_str: str) -> bool:
        """
        Perform swap exactly like JS implementation:
        - Check if native ANKR swap
        - If not native, approve router
        - Encode inner swap with function selector 0x1679c792
        - Encode multicall with function selector 0x5ae401dc
        - Send transaction
        """
        try:
            amount_in = float(amount_in_str)
            if amount_in <= 0:
                raise Exception(f"Invalid amount: {amount_in_str}")
            
            # Convert amount to wei
            amount_in_wei = self.web3.convert_to_wei(amount_in, token_in['decimals'])
            is_native_swap_in = token_in['symbol'] == 'ANKR'
            
            # Approve router if not native token
            if not is_native_swap_in:

                token_contract = self.web3.web3.eth.contract(
                    address=self.web3.web3.to_checksum_address(token_in['address']),
                    abi=ERC20_ABI
                )
                allowance = await token_contract.functions.allowance(
                    self.wallet.address,
                    SWAP_ROUTER_ADDRESS
                ).call()
                
                if allowance < amount_in_wei:
                    approve_tx = await token_contract.functions.approve(
                        self.web3.web3.to_checksum_address(SWAP_ROUTER_ADDRESS),
                        2**256 - 1
                    ).build_transaction({
                        'chainId': await self.web3.web3.eth.chain_id,
                        'from': self.wallet.address,
                        'nonce': await self.web3.web3.eth.get_transaction_count(self.wallet.address),
                        'gasPrice': await self.web3.web3.eth.gas_price,
                    })
                    approve_tx['gas'] = await self.web3.web3.eth.estimate_gas(approve_tx)
                    
                    signed_approve = self.web3.web3.eth.account.sign_transaction(approve_tx, self.wallet.key)
                    approve_hash = await self.web3.web3.eth.send_raw_transaction(signed_approve.raw_transaction)
                    approve_receipt = await self.web3.web3.eth.wait_for_transaction_receipt(approve_hash)
                    
                    if approve_receipt['status'] != 1:
                        raise Exception('Approve transaction failed')
                    logger.success(f"{self.account_index} | Approval successful")
                
            
            # Prepare swap parameters
            deadline_ms = int(time.time() * 1000) + (20 * 60 * 1000)
            token_in_address_for_router = WANKR_ADDRESS if is_native_swap_in else token_in['address']
            
            # Check if swapping TO native ANKR
            is_native_swap_out = token_out['symbol'] == 'ANKR'
            token_out_address_for_router = WANKR_ADDRESS if is_native_swap_out else token_out['address']
            
            # Encode inner swap - recipient is 0x0 if unwrapping to native, otherwise wallet
            recipient_address = '0x0000000000000000000000000000000000000000' if is_native_swap_out else self.wallet.address
            inner = self.encode_inner_swap(
                token_in=token_in_address_for_router,
                token_out=token_out_address_for_router,
                recipient=recipient_address,
                deadline_ms=deadline_ms,
                amount_in_wei=amount_in_wei
            )
            
            # Prepare multicall calls
            from eth_abi import encode as eth_encode
            calls = [bytes.fromhex(inner[2:])]
            
            # If swapping TO native ANKR, add unwrapWNativeToken call
            if is_native_swap_out:
                # Function selector: 0x69bc35b2 for unwrapWNativeToken(uint256 minAmount, address recipient)
                unwrap_params = eth_encode(
                    ['uint256', 'address'],
                    [0, self.web3.web3.to_checksum_address(self.wallet.address)]
                )
                unwrap_call = bytes.fromhex('69bc35b2' + unwrap_params.hex())
                calls.append(unwrap_call)
            
            # Encode multicall using contract interface
            from src.model.neuraverse.constants import SWAP_ROUTER_ABI
            router_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(SWAP_ROUTER_ADDRESS),
                abi=SWAP_ROUTER_ABI
            )
            
            # Prepare transaction
            tx_value = amount_in_wei if is_native_swap_in else 0

            # Build transaction using contract interface
            tx = await router_contract.functions.multicall(calls).build_transaction({
                'chainId': await self.web3.web3.eth.chain_id,
                'from': self.wallet.address,
                'nonce': await self.web3.web3.eth.get_transaction_count(self.wallet.address),
                'gasPrice': await self.web3.web3.eth.gas_price,
                'value': tx_value,
                'gas': 600_000,
            })
            
            # Sign and send
            signed_tx = self.web3.web3.eth.account.sign_transaction(tx, self.wallet.key)
            tx_hash = await self.web3.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            # Wait for receipt
            rcpt = await self.web3.web3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
            
            if rcpt['status'] != 1:
                raise Exception('Swap tx reverted on-chain')
            
            from src.utils.constants import EXPLORER_URL_NEURAVERSE
            tx_url = f"{EXPLORER_URL_NEURAVERSE}{rcpt['transactionHash'].hex()}"
            logger.success(f"{self.account_index} | Swap successful: {tx_url}")
            return True
            
        except Exception as e:
            msg = str(e)
            logger.error(f"{self.account_index} | Swap failed: {msg}")
            raise

    async def auto_swap(self) -> bool:
        """Simple swap logic matching JS implementation - just swap ANKR back and forth"""
        try:
            logger.info(f"{self.account_index} | Starting auto swap")
            
            if not self.available_tokens:
                await self.fetch_available_tokens()
            
            if not self.available_tokens or len(self.available_tokens) < 2:
                logger.error(f"{self.account_index} | Not enough tokens available")
                return False
            
            # Find ANKR and other tokens
            ankr_token = next((t for t in self.available_tokens if t['symbol'] == 'ANKR'), None)
            if not ankr_token:
                logger.error(f"{self.account_index} | ANKR token not found")
                return False
            
            # Filter tokens - exclude ANKR and USDC (problematic)
            other_tokens = [t for t in self.available_tokens if t['symbol'] not in ['ANKR', 'USDC']]
            if not other_tokens:
                logger.error(f"{self.account_index} | No other tokens available")
                return False
            
            # Check ANKR balance
            logger.info(f"{self.account_index} | Checking ANKR balance...")
            ankr_balance = await self.get_token_balance(ankr_token['address'])
            MIN_BALANCE = 0.5
            if not ankr_balance or ankr_balance.formatted < MIN_BALANCE:
                logger.warning(f"{self.account_index} | ANKR balance too low ({ankr_balance.formatted if ankr_balance else 0:.6f} < {MIN_BALANCE}), skipping swaps")
                return False
            
            # Get number of swaps from config and calculate cycles
            total_swaps = random.randint(
                self.config.ZOTTO.NUMBER_OF_SWAPS[0],
                self.config.ZOTTO.NUMBER_OF_SWAPS[1]
            )
            # Round down to even number and divide by 2 to get cycles
            total_swaps = total_swaps if total_swaps % 2 == 0 else total_swaps - 1
            num_cycles = total_swaps // 2
            logger.info(f"{self.account_index} | Will perform {num_cycles} swap cycles ({total_swaps} total swaps)")
            
            # Perform multiple swap cycles
            for i in range(num_cycles):
                logger.info(f"{self.account_index} | Swap cycle {i + 1}/{num_cycles}")
                
                # Pick random token
                token_to = random.choice(other_tokens)
                
                # Check ANKR balance before each cycle
                ankr_balance = await self.get_token_balance(ankr_token['address'])
                if not ankr_balance or ankr_balance.formatted < 0.3:
                    logger.warning(f"{self.account_index} | ANKR balance too low, stopping swaps")
                    break
                
                # Reserve gas
                gas_reserve = 0.1
                available_balance = max(0, ankr_balance.formatted - gas_reserve)
                
                # Calculate swap amount from config
                swap_percent = random.uniform(
                    self.config.ZOTTO.BALANCE_PERCENT_TO_SWAP[0] / 100,
                    self.config.ZOTTO.BALANCE_PERCENT_TO_SWAP[1] / 100
                )
                swap_amount = available_balance * swap_percent
                
                if swap_amount < 0.0001:
                    logger.warning(f"{self.account_index} | Swap amount too small: {swap_amount}")
                    continue
                
                success = await self.perform_swap(ankr_token, token_to, str(swap_amount))
                if not success:
                    continue
                
                # Wait between swaps
                pause = random.randint(
                    self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                    self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1]
                )
                logger.info(f"{self.account_index} | Waiting {pause}s before reverse swap...")
                await asyncio.sleep(pause)
                
                to_balance = await self.get_token_balance(token_to['address'])
                if to_balance and to_balance.formatted > 0.0001:
                    swap_back_amount = to_balance.formatted * 0.99
                    logger.info(f"{self.account_index} | Swapping {swap_back_amount} {token_to['symbol']} → ANKR")
                    await self.perform_swap(token_to, ankr_token, str(swap_back_amount))
                else:
                    logger.warning(f"{self.account_index} | No {token_to['symbol']} balance to swap back")
                
                # Wait before next cycle
                if i < num_cycles - 1:
                    pause = random.randint(
                        self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0],
                        self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1]
                    )
                    logger.info(f"{self.account_index} | Waiting {pause}s before next cycle...")
                    await asyncio.sleep(pause)
            
            logger.success(f"{self.account_index} | Auto swap completed")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Auto swap error: {e}")
            return False

    async def _connect_sepolia_web3(self) -> None:
        """Initialize Sepolia Web3 connection if not already connected"""
        if self.sepolia_web3 is None:
            try:
                proxy_settings = None
                if self.neuraverse.proxy:
                    proxy_settings = f"http://{self.neuraverse.proxy}"
                
                self.sepolia_web3 = AsyncWeb3(
                    AsyncWeb3.AsyncHTTPProvider(
                        SEPOLIA_RPC,
                        request_kwargs={
                            "proxy": proxy_settings,
                            "ssl": False,
                        },
                    )
                )
                # Test connection
                await self.sepolia_web3.eth.chain_id
                logger.info(f"{self.account_index} | Connected to Sepolia network")
            except Exception as e:
                logger.error(f"{self.account_index} | Failed to connect to Sepolia: {e}")
                raise

    @retry_async(default_value=None)
    async def wait_for_neura_balance(self, min_amount: float = 0.001, max_attempts: int = 15, step_ms: int = 5000) -> bool:
        """
        Wait for native ANKR balance on Neura to reach minimum amount
        
        Args:
            min_amount: Minimum balance required in ANKR
            max_attempts: Maximum number of attempts to check
            step_ms: Delay between checks in milliseconds
        
        Returns:
            True if balance reached, False if timeout
        """
        try:
            logger.info(f"{self.account_index} | Waiting for ANKR balance to be at least {min_amount} ANKR...")
            min_wei = self.web3.convert_to_wei(min_amount, 18)
            
            for i in range(max_attempts):
                balance = await self.web3.get_balance(self.wallet.address)
                logger.info(f"{self.account_index} | Attempt {i+1}/{max_attempts}: Current balance is {balance.formatted} ANKR")
                
                if balance.wei >= min_wei:
                    logger.success(f"{self.account_index} | Balance is sufficient!")
                    return True
                
                await asyncio.sleep(step_ms / 1000)
            
            logger.error(f"{self.account_index} | Timeout: Balance did not reach {min_amount} ANKR")
            return False
        except Exception as e:
            logger.error(f"{self.account_index} | Error waiting for balance: {e}")
            return False

    @retry_async(default_value=False)
    async def bridge_neura_to_sepolia(self, amount_eth: str) -> bool:
        """
        Bridge ANKR from Neura to Sepolia
        
        Args:
            amount_eth: Amount to bridge in ANKR (as string)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            amount = float(amount_eth)
            if amount <= 0:
                raise Exception(f"Invalid amount: {amount_eth}")
            
            logger.info(f"{self.account_index} | Bridging {amount} ANKR from Neura → Sepolia...")
            
            amount_wei = self.web3.convert_to_wei(amount, 18)
            
            # Create bridge contract instance
            bridge_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(NEURA_BRIDGE_ADDRESS),
                abi=NEURA_BRIDGE_ABI
            )
            
            # Build transaction
            tx = await bridge_contract.functions.deposit(
                self.wallet.address,
                SEPOLIA_CHAIN_ID
            ).build_transaction({
                'chainId': await self.web3.web3.eth.chain_id,
                'from': self.wallet.address,
                'nonce': await self.web3.web3.eth.get_transaction_count(self.wallet.address),
                'gasPrice': await self.web3.web3.eth.gas_price,
                'value': amount_wei,
            })
            
            # Estimate gas with buffer
            tx['gas'] = await self.web3.web3.eth.estimate_gas(tx)
            
            # Sign and send
            signed_tx = self.web3.web3.eth.account.sign_transaction(tx, self.wallet.key)
            tx_hash = await self.web3.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f"{self.account_index} | Bridge deposit tx: {tx_hash.hex()}")
            
            # Wait for receipt
            rcpt = await self.web3.web3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
            
            if rcpt['status'] != 1:
                raise Exception('Bridge deposit transaction failed')
            
            from src.utils.constants import EXPLORER_URL_NEURAVERSE
            tx_url = f"{EXPLORER_URL_NEURAVERSE}{rcpt['transactionHash'].hex()}"
            logger.success(f"{self.account_index} | Bridge deposit confirmed: {tx_url}")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge Neura→Sepolia failed: {e}")
            raise

    @retry_async(default_value=False)
    async def bridge_sepolia_to_neura(self, amount_eth: str) -> bool:
        """
        Bridge tANKR from Sepolia to Neura
        
        Args:
            amount_eth: Amount to bridge in tANKR (as string)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            amount = float(amount_eth)
            if amount <= 0:
                raise Exception(f"Invalid amount: {amount_eth}")
            
            logger.info(f"{self.account_index} | Bridging {amount} tANKR from Sepolia → Neura...")
            
            # Connect to Sepolia
            await self._connect_sepolia_web3()
            
            amount_wei = int(amount * 10**18)
            
            # Token contract
            token_contract = self.sepolia_web3.eth.contract(
                address=self.sepolia_web3.to_checksum_address(SEPOLIA_TANKR_ADDRESS),
                abi=ERC20_ABI
            )
            
            # Bridge contract
            bridge_contract = self.sepolia_web3.eth.contract(
                address=self.sepolia_web3.to_checksum_address(SEPOLIA_BRIDGE_ADDRESS),
                abi=SEPOLIA_BRIDGE_ABI
            )
            
            # Check allowance
            allowance = await token_contract.functions.allowance(
                self.wallet.address,
                SEPOLIA_BRIDGE_ADDRESS
            ).call()
            
            if allowance < amount_wei:
                logger.info(f"{self.account_index} | Approving bridge to spend tANKR...")
                
                approve_tx = await token_contract.functions.approve(
                    self.sepolia_web3.to_checksum_address(SEPOLIA_BRIDGE_ADDRESS),
                    2**256 - 1
                ).build_transaction({
                    'chainId': await self.sepolia_web3.eth.chain_id,
                    'from': self.wallet.address,
                    'nonce': await self.sepolia_web3.eth.get_transaction_count(self.wallet.address),
                    'gasPrice': await self.sepolia_web3.eth.gas_price,
                })
                approve_tx['gas'] = await self.sepolia_web3.eth.estimate_gas(approve_tx)
                
                signed_approve = self.sepolia_web3.eth.account.sign_transaction(approve_tx, self.wallet.key)
                approve_hash = await self.sepolia_web3.eth.send_raw_transaction(signed_approve.raw_transaction)
                await self.sepolia_web3.eth.wait_for_transaction_receipt(approve_hash)
                
                logger.success(f"{self.account_index} | Approval successful")
            else:
                logger.info(f"{self.account_index} | Sufficient allowance already set")
            
            # Deposit to bridge
            logger.info(f"{self.account_index} | Depositing tANKR to bridge...")
            
            deposit_tx = await bridge_contract.functions.deposit(
                amount_wei,
                self.wallet.address
            ).build_transaction({
                'chainId': await self.sepolia_web3.eth.chain_id,
                'from': self.wallet.address,
                'nonce': await self.sepolia_web3.eth.get_transaction_count(self.wallet.address),
                'gasPrice': await self.sepolia_web3.eth.gas_price,
            })
            deposit_tx['gas'] = await self.sepolia_web3.eth.estimate_gas(deposit_tx)
            
            signed_deposit = self.sepolia_web3.eth.account.sign_transaction(deposit_tx, self.wallet.key)
            deposit_hash = await self.sepolia_web3.eth.send_raw_transaction(signed_deposit.raw_transaction)
            rcpt = await self.sepolia_web3.eth.wait_for_transaction_receipt(deposit_hash)
            
            if rcpt['status'] != 1:
                raise Exception('Bridge deposit failed')
            
            logger.success(f"{self.account_index} | Bridge deposit (Sepolia) OK: {deposit_hash.hex()}")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge Sepolia→Neura failed: {e}")
            raise

    @retry_async(default_value=False)
    async def claim_validated_on_sepolia(self, wait_ms: int = 60000, page: int = 1, limit: int = 20) -> bool:
        """
        Auto-claim pending bridge transactions on Sepolia
        
        Args:
            wait_ms: Time to wait before checking for claims (in milliseconds)
            page: Page number for claim list
            limit: Number of items per page
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"{self.account_index} | Auto-claim Pending Bridge Tx...")
            
            # Wait before checking
            if wait_ms > 0:
                logger.info(f"{self.account_index} | Waiting {wait_ms/1000}s before checking claims...")
                await asyncio.sleep(wait_ms / 1000)
            
            # Connect to Sepolia
            await self._connect_sepolia_web3()
            
            # Fetch claim list from API
            url = f"https://neuraverse-testnet.infra.neuraprotocol.io/api/claim-tx?recipient={self.wallet.address.lower()}&page={page}&limit={limit}"
            
            headers = {
                'accept': 'application/json',
                'origin': 'https://neuraverse.neuraprotocol.io',
                'referer': 'https://neuraverse.neuraprotocol.io/',
            }
            
            # Add authorization if available
            if hasattr(self.neuraverse, 'identity_token') and self.neuraverse.identity_token:
                headers['Authorization'] = f'Bearer {self.neuraverse.identity_token}'
            
            logger.info(f"{self.account_index} | Fetching claim list...")
            
            response = await self.neuraverse.session.get(url, headers=headers)
            if response.status_code != 200:
                logger.warning(f"{self.account_index} | Failed to fetch claim list: {response.status_code}")
                return False
            
            data = response.json()
            items = data.get('transactions', [])
            
            if not items:
                logger.info(f"{self.account_index} | No transactions to claim")
                return True
            
            # Filter claimable transactions
            to_claim = [
                x for x in items
                if str(x.get('chainId')) == str(SEPOLIA_CHAIN_ID)
                and x.get('status') == 'validated'
                and x.get('encodedMessage')
                and isinstance(x.get('messageSignatures'), list)
                and len(x.get('messageSignatures', [])) > 0
            ]
            
            if not to_claim:
                logger.info(f"{self.account_index} | No validated transactions to claim")
                return True
            
            logger.info(f"{self.account_index} | Found {len(to_claim)} validated tx to claim on Sepolia")
            
            # Claim contract
            claim_contract = self.sepolia_web3.eth.contract(
                address=self.sepolia_web3.to_checksum_address(SEPOLIA_BRIDGE_ADDRESS),
                abi=BRIDGE_CLAIM_ABI
            )
            
            for tx_info in to_claim:
                tx_hash_short = tx_info.get('transactionHash', tx_info.get('id', '0x...'))[:10]
                try:
                    logger.info(f"{self.account_index} | Claiming {tx_hash_short}...")
                    
                    encoded_message = tx_info['encodedMessage']
                    message_signatures = tx_info['messageSignatures']
                    
                    # Convert to bytes
                    if isinstance(encoded_message, str):
                        if encoded_message.startswith('0x'):
                            encoded_message = bytes.fromhex(encoded_message[2:])
                        else:
                            encoded_message = bytes.fromhex(encoded_message)
                    
                    signatures_bytes = []
                    for sig in message_signatures:
                        if isinstance(sig, str):
                            if sig.startswith('0x'):
                                signatures_bytes.append(bytes.fromhex(sig[2:]))
                            else:
                                signatures_bytes.append(bytes.fromhex(sig))
                        else:
                            signatures_bytes.append(sig)
                    
                    claim_tx = await claim_contract.functions.claim(
                        encoded_message,
                        signatures_bytes
                    ).build_transaction({
                        'chainId': await self.sepolia_web3.eth.chain_id,
                        'from': self.wallet.address,
                        'nonce': await self.sepolia_web3.eth.get_transaction_count(self.wallet.address),
                        'gasPrice': await self.sepolia_web3.eth.gas_price,
                    })
                    claim_tx['gas'] = await self.sepolia_web3.eth.estimate_gas(claim_tx)
                    
                    signed_claim = self.sepolia_web3.eth.account.sign_transaction(claim_tx, self.wallet.key)
                    claim_hash = await self.sepolia_web3.eth.send_raw_transaction(signed_claim.raw_transaction)
                    rcpt = await self.sepolia_web3.eth.wait_for_transaction_receipt(claim_hash)
                    
                    if rcpt['status'] != 1:
                        raise Exception('Claim tx reverted')
                    
                    logger.success(f"{self.account_index} | Claim OK: {claim_hash.hex()}")
                    
                except Exception as e:
                    error_msg = str(e)
                    if 'already claimed' in error_msg.lower() or 'already processed' in error_msg.lower() or 'duplicate' in error_msg.lower():
                        logger.warning(f"{self.account_index} | Skip (Already claimed): {tx_hash_short}")
                        continue
                    logger.error(f"{self.account_index} | Failed to claim {tx_hash_short}: {error_msg}")
            
            logger.success(f"{self.account_index} | Claim process completed")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Failed to claim validated transactions: {e}")
            return False

    async def auto_bridge(self) -> bool:
        """
        Auto bridge based on config settings:
        - If both BRIDGE_ALL_TO_SEPOLIA and BRIDGE_ALL_TO_ANKR are TRUE -> bridge from Neura to Sepolia
        - If only BRIDGE_ALL_TO_SEPOLIA is TRUE -> bridge all from Neura to Sepolia
        - If only BRIDGE_ALL_TO_ANKR is TRUE -> bridge all from Sepolia to Neura
        - If both are FALSE -> random direction using percent settings
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"{self.account_index} | Starting auto bridge")
            
            bridge_all_to_sepolia = self.config.BRIDGE.BRIDGE_ALL_TO_SEPOLIA
            bridge_all_to_ankr = self.config.BRIDGE.BRIDGE_ALL_TO_ANKR
            
            # Determine bridge direction based on config
            if bridge_all_to_sepolia and bridge_all_to_ankr:
                # Both true -> bridge from Neura to Sepolia
                logger.info(f"{self.account_index} | Config: Bridge ALL from Neura → Sepolia")
                return await self._bridge_neura_to_sepolia_all()
                
            elif bridge_all_to_sepolia and not bridge_all_to_ankr:
                # Only Sepolia true -> bridge all from Neura to Sepolia
                logger.info(f"{self.account_index} | Config: Bridge ALL from Neura → Sepolia")
                return await self._bridge_neura_to_sepolia_all()
                
            elif not bridge_all_to_sepolia and bridge_all_to_ankr:
                # Only ANKR true -> bridge all from Sepolia to Neura
                logger.info(f"{self.account_index} | Config: Bridge ALL from Sepolia → Neura")
                return await self._bridge_sepolia_to_neura_all()
                
            else:
                # Both false -> random direction with percent
                # If source has low balance, try opposite direction
                direction = random.choice(['neura_to_sepolia', 'sepolia_to_neura'])
                logger.info(f"{self.account_index} | Config: Random bridge direction -> {direction}")
                
                if direction == 'neura_to_sepolia':
                    result = await self._bridge_neura_to_sepolia_percent()
                    if not result:
                        logger.info(f"{self.account_index} | Neura balance too low, trying Sepolia → Neura instead")
                        return await self._bridge_sepolia_to_neura_percent()
                    return result
                else:
                    result = await self._bridge_sepolia_to_neura_percent()
                    if not result:
                        logger.info(f"{self.account_index} | Sepolia balance too low, trying Neura → Sepolia instead")
                        return await self._bridge_neura_to_sepolia_percent()
                    return result
                    
        except Exception as e:
            logger.error(f"{self.account_index} | Auto bridge error: {e}")
            return False

    async def _bridge_neura_to_sepolia_all(self) -> bool:
        """Bridge ALL available ANKR from Neura to Sepolia"""
        try:
            # Check ANKR balance on Neura
            ankr_balance = await self.web3.get_balance(self.wallet.address)
            MIN_BALANCE = 0.01
            GAS_RESERVE = 0.005  # Reserve for gas
            
            if not ankr_balance or ankr_balance.formatted < MIN_BALANCE:
                logger.warning(f"{self.account_index} | ANKR balance too low ({ankr_balance.formatted if ankr_balance else 0:.6f} < {MIN_BALANCE}), skipping bridge")
                return False
            
            # Calculate amount to bridge (all minus gas reserve)
            bridge_amount = max(0, ankr_balance.formatted - GAS_RESERVE)
            
            if bridge_amount < 0.001:
                logger.warning(f"{self.account_index} | Amount to bridge too small: {bridge_amount}")
                return False
            
            logger.info(f"{self.account_index} | Bridging {bridge_amount} ANKR (ALL) from Neura → Sepolia")
            
            # Bridge to Sepolia
            success = await self.bridge_neura_to_sepolia(str(bridge_amount))
            if not success:
                return False
            
            # Wait and claim on Sepolia
            logger.info(f"{self.account_index} | Waiting before claiming on Sepolia...")
            await asyncio.sleep(60)  # Wait 1 minute for validation
            
            await self.claim_validated_on_sepolia(wait_ms=0)
            
            logger.success(f"{self.account_index} | Bridge Neura → Sepolia completed")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge Neura → Sepolia (all) failed: {e}")
            return False

    async def _bridge_sepolia_to_neura_all(self) -> bool:
        """Bridge ALL available tANKR from Sepolia to Neura"""
        try:
            # Connect to Sepolia
            await self._connect_sepolia_web3()
            
            # Check tANKR balance on Sepolia
            token_contract = self.sepolia_web3.eth.contract(
                address=self.sepolia_web3.to_checksum_address(SEPOLIA_TANKR_ADDRESS),
                abi=ERC20_ABI
            )
            
            tankr_balance_wei = await token_contract.functions.balanceOf(self.wallet.address).call()
            tankr_balance = tankr_balance_wei / 10**18
            
            MIN_BALANCE = 0.001
            
            if tankr_balance < MIN_BALANCE:
                logger.warning(f"{self.account_index} | tANKR balance too low ({tankr_balance:.6f} < {MIN_BALANCE}), skipping bridge")
                return False
            
            logger.info(f"{self.account_index} | Bridging {tankr_balance} tANKR (ALL) from Sepolia → Neura")
            
            # Bridge to Neura
            success = await self.bridge_sepolia_to_neura(str(tankr_balance))
            if not success:
                return False
            
            logger.success(f"{self.account_index} | Bridge Sepolia → Neura completed")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge Sepolia → Neura (all) failed: {e}")
            return False

    async def _bridge_neura_to_sepolia_percent(self) -> bool:
        """Bridge percentage of ANKR from Neura to Sepolia"""
        try:
            # Check ANKR balance on Neura
            ankr_balance = await self.web3.get_balance(self.wallet.address)
            MIN_BALANCE = 0.1
            GAS_RESERVE = 0.005
            
            if not ankr_balance or ankr_balance.formatted < MIN_BALANCE:
                logger.warning(f"{self.account_index} | ANKR balance too low ({ankr_balance.formatted if ankr_balance else 0:.6f} < {MIN_BALANCE}), skipping bridge")
                return False
            
            # Calculate bridge amount using percentage
            available_balance = max(0, ankr_balance.formatted - GAS_RESERVE)
            bridge_percent = random.uniform(
                self.config.BRIDGE.ANKR_BALANCE_PERCENT_TO_BRIDGE[0] / 100,
                self.config.BRIDGE.ANKR_BALANCE_PERCENT_TO_BRIDGE[1] / 100
            )
            bridge_amount = available_balance * bridge_percent
            
            if bridge_amount < 0.001:
                logger.warning(f"{self.account_index} | Bridge amount too small: {bridge_amount}")
                return False
            
            logger.info(f"{self.account_index} | Bridging {bridge_amount:.6f} ANKR ({bridge_percent*100:.1f}%) from Neura → Sepolia")
            
            # Bridge to Sepolia
            success = await self.bridge_neura_to_sepolia(str(bridge_amount))
            if not success:
                return False
            
            # Wait and claim on Sepolia
            logger.info(f"{self.account_index} | Waiting before claiming on Sepolia...")
            await asyncio.sleep(60)
            
            await self.claim_validated_on_sepolia(wait_ms=0)
            
            logger.success(f"{self.account_index} | Bridge Neura → Sepolia completed")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge Neura → Sepolia (percent) failed: {e}")
            return False

    async def _bridge_sepolia_to_neura_percent(self) -> bool:
        """Bridge percentage of tANKR from Sepolia to Neura"""
        try:
            # Connect to Sepolia
            await self._connect_sepolia_web3()
            
            # Check tANKR balance on Sepolia
            token_contract = self.sepolia_web3.eth.contract(
                address=self.sepolia_web3.to_checksum_address(SEPOLIA_TANKR_ADDRESS),
                abi=ERC20_ABI
            )
            
            tankr_balance_wei = await token_contract.functions.balanceOf(self.wallet.address).call()
            tankr_balance = tankr_balance_wei / 10**18
            
            MIN_BALANCE = 0.01
            
            if tankr_balance < MIN_BALANCE:
                logger.warning(f"{self.account_index} | tANKR balance too low ({tankr_balance:.6f} < {MIN_BALANCE}), skipping bridge")
                return False
            
            # Calculate bridge amount using percentage
            bridge_percent = random.uniform(
                self.config.BRIDGE.SEPOLIA_BALANCE_PERCENT_TO_BRIDGE[0] / 100,
                self.config.BRIDGE.SEPOLIA_BALANCE_PERCENT_TO_BRIDGE[1] / 100
            )
            bridge_amount = tankr_balance * bridge_percent
            
            if bridge_amount < 0.001:
                logger.warning(f"{self.account_index} | Bridge amount too small: {bridge_amount}")
                return False
            
            logger.info(f"{self.account_index} | Bridging {bridge_amount:.6f} tANKR ({bridge_percent*100:.1f}%) from Sepolia → Neura")
            
            # Bridge to Neura
            success = await self.bridge_sepolia_to_neura(str(bridge_amount))
            if not success:
                return False
            
            logger.success(f"{self.account_index} | Bridge Sepolia → Neura completed")
            return True
            
        except Exception as e:
            logger.error(f"{self.account_index} | Bridge Sepolia → Neura (percent) failed: {e}")
            return False
