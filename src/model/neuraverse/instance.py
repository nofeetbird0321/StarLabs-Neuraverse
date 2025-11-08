import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

import primp
from eth_account import Account
from eth_account.messages import encode_defunct
from loguru import logger

from src.model.neuraverse.swaps import NeuraSwaps
from src.model.help.captcha import Capsolver, Solvium
from src.model.neuraverse.connect_socials import ConnectSocials
from src.model.neuraverse.leaderboard import Leaderboard
from src.model.onchain.web3_custom import Web3Custom
from src.utils.config import Config
from src.utils.decorators import retry_async


class Neuraverse:
    def __init__(
        self,
        account_index: int,
        session: primp.AsyncClient,
        web3: Web3Custom,
        config: Config,
        wallet: Account,
        proxy: str,
        discord_token: str,
        twitter_token: str,
    ):
        self.account_index = account_index
        self.session = session
        self.web3 = web3
        self.config = config
        self.wallet = wallet
        self.proxy = proxy
        self.discord_token = discord_token
        self.twitter_token = twitter_token

        self.privy_session_token = None # used as privy-token in cookies
        self.identity_token = None # used as Bearer in headers or privy-id-token in cookies
        self.privy_refresh_token = None
        self.privy_ca_id = None

    async def login(self) -> bool:
        try:
            nonce, expires_at = await self.init_privy_auth()
            
            expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            issued_at_dt = expires_dt - timedelta(minutes=10)
            issued_at = issued_at_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            
            response_json, cookies_dict = await self.authenticate_privy(nonce, issued_at)
            if response_json:
                is_new_user = response_json.get("is_new_user", False)
                if is_new_user:
                    return await self.create_new_user(cookies_dict)
                else:
                    return True
            else:
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Login error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False
    
    @retry_async(default_value=False)
    async def init_privy_auth(self) -> tuple[str, str]:
        """
        Initialize Privy auth. Returns nonce (string) and expires_at (string) for authentication.
        """
        try:

            if self.config.CAPTCHA.USE_CAPSOLVER:
                logger.info(f"{self.account_index} | Solving captcha for Neuraverse login with Capsolver...")

                capsolver = Capsolver(
                    api_key=self.config.CAPTCHA.CAPSOLVER_API_KEY,
                    session=self.session,
                    proxy=self.proxy,
                )
                captcha_token = await capsolver.solve_turnstile(
                    sitekey="0x4AAAAAAAM8ceq5KhP1uJBt",
                    pageurl="https://neuraverse.neuraprotocol.io/",
                )
            else:
                logger.info(f"{self.account_index} | Solving captcha for Neuraverse login with Solvium...")

                solvium = Solvium(
                    api_key=self.config.CAPTCHA.SOLVIUM_API_KEY,
                    session=self.session,
                    proxy=self.proxy,
                )
                captcha_token = await solvium.solve_turnstile(
                    sitekey="0x4AAAAAAAM8ceq5KhP1uJBt",
                    pageurl="https://neuraverse.neuraprotocol.io/",
                )

            if captcha_token is None:
                raise Exception("Unable to solve captcha")

            logger.success(
                f"{self.account_index} | Captcha for Neuraverse solved successfully!"
            )

            self.privy_ca_id = str(uuid.uuid4())

            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'content-type': 'application/json',
                'origin': 'https://neuraverse.neuraprotocol.io',
                'priority': 'u=1, i',
                'privy-app-id': 'cmbpempz2011ll10l7iucga14',
                'privy-ca-id': self.privy_ca_id,
                'privy-client': 'react-auth:2.25.0',
                'referer': 'https://neuraverse.neuraprotocol.io/',
            }

            json_data = {
                'address': self.wallet.address,
                'token': captcha_token,
            }

            response = await self.session.post(
                url='https://privy.neuraprotocol.io/api/v1/siwe/init',
                json=json_data,
                headers=headers,
            )

            if "Access to this service has been restricted for your location" in response.text:
                logger.error(
                    f"{self.account_index} | Access to this service has been restricted for your location. Change your proxy IP or start the bot again."
                )
                return None, None

            nonce = response.json().get("nonce", None)
            expires_at = response.json().get("expires_at", None)
            if nonce is None or expires_at is None:
                    raise Exception(f"Failed to get nonce for Privy auth: {response.text}")

            return nonce, expires_at
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Init Privy auth error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=None)
    async def authenticate_privy(self, nonce: str, issued_at: str) -> tuple[dict, dict]:
        try:
            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'content-type': 'application/json',
                'origin': 'https://neuraverse.neuraprotocol.io',
                'priority': 'u=1, i',
                'privy-app-id': 'cmbpempz2011ll10l7iucga14',
                'privy-ca-id': self.privy_ca_id,
                'privy-client': 'react-auth:2.25.0',
                'referer': 'https://neuraverse.neuraprotocol.io/',
                }

            message = 'neuraverse.neuraprotocol.io wants you to sign in with your Ethereum account:\n' \
                f'{self.wallet.address}\n\n' \
                'By signing, you are proving you own this wallet and logging in. ' \
                'This does not initiate a transaction or cost any fees.\n\n' \
                'URI: https://neuraverse.neuraprotocol.io\n' \
                'Version: 1\n' \
                'Chain ID: 1625\n' \
                f'Nonce: {nonce}\n' \
                f'Issued At: {issued_at}\n' \
                'Resources:\n- https://privy.io'

            encoded_message = encode_defunct(text=message)
            signed_message = self.wallet.sign_message(encoded_message)
            signature = signed_message.signature.hex()

            json_data = {
                'message': message,
                'signature': "0x" + signature,
                'chainId': 'eip155:1625',
                'walletClientType': 'metamask',
                'connectorType': 'injected',
                'mode': 'login-or-sign-up',
            }

            response = await self.session.post(
                'https://privy.neuraprotocol.io/api/v1/siwe/authenticate',
                headers=headers,
                json=json_data,
            )

            response_json = response.json()
            
            # Extract tokens from JSON response
            self.privy_session_token = response_json.get("token", None)
            self.identity_token = response_json.get("identity_token", None)
            self.privy_refresh_token = response_json.get("refresh_token", None)
            
            # Extract tokens from cookies (they might differ from JSON response)
            response_cookies = response.cookies
            
            # Check if cookies is already a dict or needs to be converted
            if isinstance(response_cookies, dict):
                cookies_dict = response_cookies
            else:
                # Try to convert cookies collection to dict
                try:
                    cookies_dict = {cookie.name: cookie.value for cookie in response_cookies}
                except (AttributeError, TypeError):
                    # If it's a string or other format, try to parse it
                    cookies_dict = dict(response_cookies) if response_cookies else {}


            if not self.privy_session_token:
                raise Exception(f"Failed to get Privy session token: {response.text}")
            
            logger.success(
                f"{self.account_index} | Privy auth successful!"
            )
            return response_json, cookies_dict

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Init Privy auth error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    @retry_async(default_value=False)
    async def get_account_info(self) -> dict:
        """
        Get Neuraverse account info.
        Return dict:
        {
            "address": str,
            "neura_points": int,
            "trading_volume": {
                "month": int,
                "allTime": int,
            },
            "pulses": dict,
            "social_accounts": list
        }
        """
        try:
            cookies = {
                'privy-token': self.privy_session_token,
                'privy-id-token': self.identity_token,
                'privy-session': 'privy.neuraprotocol.io',
            }

            headers = {
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.identity_token}',
                'origin': 'https://neuraverse.neuraprotocol.io',
                'priority': 'u=1, i',
                'referer': 'https://neuraverse.neuraprotocol.io/',
                }

            response = await self.session.get('https://neuraverse-testnet.infra.neuraprotocol.io/api/account', cookies=cookies, headers=headers)

            response_json = response.json()

            return response_json

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Get Neuraverse account info error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def connect_socials(self) -> bool:
        try:
            connect_socials_service = ConnectSocials(self)
            return await connect_socials_service.connect_socials()

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Connect socials error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    async def complete_quests(self) -> bool:
        try:
            complete_quests_service = Leaderboard(self)
            return await complete_quests_service.complete_quests()
            
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Complete quests error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    async def perform_swaps(self) -> bool:
        try:
            swaps_service = NeuraSwaps(self)
            return await swaps_service.auto_swap()
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Perform swaps error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False


    async def perform_bridge(self) -> bool:
        try:
            bridge_service = NeuraSwaps(self)
            return await bridge_service.auto_bridge()
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Perform bridge error: {e}. Sleeping {random_pause} seconds..."
            )

    retry_async(default_value=False)
    async def create_new_user(self, cookies_dict: dict) -> bool:
        try:
            cookies = {
                'privy-token': cookies_dict['privy-token'],
                'privy-id-token': cookies_dict['privy-id-token'],
                'privy-refresh-token': cookies_dict['privy-refresh-token'],
                'privy-session': 'privy.neuraprotocol.io',
                'privy-access-token': cookies_dict['privy-access-token'],
               }
            
            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5',
                'authorization': f'Bearer {self.privy_session_token}',
                'content-type': 'application/json',
                'origin': 'https://neuraverse.neuraprotocol.io',
                'priority': 'u=1, i',
                'privy-app-id': 'cmbpempz2011ll10l7iucga14',
                'privy-ca-id': self.privy_ca_id,
                'privy-client': 'react-auth:2.25.0',
                'referer': 'https://neuraverse.neuraprotocol.io/',
               }

            utc_time_now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            
            json_data = {
                'event_name': 'sdk_authenticate',
                'client_id': self.privy_ca_id,
                'payload': {
                    'method': 'siwe',
                    'isNewUser': True,
                    'clientTimestamp': utc_time_now,
                },
            }

            await self.session.post(
                'https://privy.neuraprotocol.io/api/v1/analytics_events',
                cookies=cookies,
                headers=headers,
                json=json_data,
            )

            json_data = {
                'event_name': 'sdk_authenticate_siwe',
                'client_id': self.privy_ca_id,
                'payload': {
                    'connectorType': 'injected',
                    'walletClientType': 'metamask',
                    'clientTimestamp': utc_time_now,
                },
            }

            await self.session.post(
                'https://privy.neuraprotocol.io/api/v1/analytics_events',
                cookies=cookies,
                headers=headers,
                json=json_data,
            )

            return True

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.account_index}] | Create new user error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise