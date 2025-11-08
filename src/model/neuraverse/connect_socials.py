import asyncio
import random

from loguru import logger

from src.model.neuraverse.constants import NeuraverseProtocol
from src.utils.decorators import retry_async


class ConnectSocials:
    def __init__(self, neuraverse_instance: NeuraverseProtocol):
        self.neuraverse = neuraverse_instance

    async def connect_socials(self):
        try:
            success = True
            logger.info(f"{self.neuraverse.account_index} | Starting connect socials...")

            account_info = await self.neuraverse.get_account_info()

            if account_info is None:
                raise Exception("Account info is None")

            if account_info["social_accounts"]["twitter"]["id"] == "":
                if not self.neuraverse.twitter_token:
                    logger.error(
                        f"{self.neuraverse.account_index} | Twitter token is None. Please add token to data/twitter_tokens.txt"
                    )
                else:
                    if not await self.connect_twitter():
                        success = False
            else:
                logger.success(
                    f"{self.neuraverse.account_index} | Twitter already connected"
                )

            if account_info["social_accounts"]["discord"]["id"] == "":
                if not self.neuraverse.discord_token:
                    logger.error(
                        f"{self.neuraverse.account_index} | Discord token is None. Please add token to data/discord_tokens.txt"
                    )
                else:
                    if not await self.connect_discord():
                        success = False
            else:
                logger.success(
                    f"{self.neuraverse.account_index} | Discord already connected"
                )

            if success:
                logger.success(
                    f"{self.neuraverse.account_index} | Successfully connected socials"
                )
            else:
                logger.error(f"{self.neuraverse.account_index} | Failed to connect socials")

            return success

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.neuraverse.account_index} | Connect socials error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False
