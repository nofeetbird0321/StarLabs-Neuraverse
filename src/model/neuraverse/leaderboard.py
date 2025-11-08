import asyncio
import random

from loguru import logger

from src.model.neuraverse.constants import (
    SUPPORTED_GAME_VISIT_LOCATIONS_IDS,
    NeuraverseProtocol,
    SUPPORTED_LEADERBOARD_QUESTS_IDS,
)
from src.utils.decorators import retry_async


class Leaderboard:
    def __init__(self, neuraverse_instance: NeuraverseProtocol):
        self.neuraverse = neuraverse_instance

    async def complete_quests(self) -> bool:
        try:
            all_quests = await self.get_all_quests()
            if not all_quests:
                logger.error(
                    f"[{self.neuraverse.account_index}] | Unable to get leaderboard quests"
                )
                return False

            faucet_quest = None
            other_quests = []
            for quest in all_quests:
                if quest.get("id") == "claim_faucet":
                    faucet_quest = quest
                else:
                    other_quests.append(quest)
            
            random.shuffle(other_quests)
            
            if faucet_quest:
                all_quests = other_quests + [faucet_quest]
            else:
                all_quests = other_quests

            total_quests = len(all_quests)
            claimable_quests = sum(
                1 for q in all_quests if q.get("status") == "claimable"
            )
            not_completed_quests = sum(
                1 for q in all_quests if q.get("status") == "notCompleted"
            )
            logger.info(
                f"[{self.neuraverse.account_index}] | Quests: {claimable_quests} claimable, {not_completed_quests}/{total_quests} not completed"
            )

            claimed_quests = 0
            completed_quests = 0
            claim_failed = 0
            complete_failed = 0

            for quest in all_quests:
                quest_status = quest.get("status")
                quest_id = quest.get("id")
                quest_name = quest.get("name")

                try:
                    if quest_status == "notCompleted":
                        if quest_id not in SUPPORTED_LEADERBOARD_QUESTS_IDS:
                            # logger.warning(
                            #     f"[{self.neuraverse.account_index}] | Quest {quest_name} not supported yet"
                            # )
                            continue

                        if not await self.complete_quest(quest):
                            complete_failed += 1
                        else:
                            completed_quests += 1
                            await asyncio.sleep(5)
                            if not await self.claim_quest(quest):
                                claim_failed += 1
                            else:
                                claimed_quests += 1

                    if quest_status == "claimable":
                        if not await self.claim_quest(quest):
                            claim_failed += 1
                        else:
                            claimed_quests += 1
                except Exception as e:
                    logger.error(
                        f"[{self.neuraverse.account_index}] | Failed to process quest {quest_name}: {e}"
                    )
                    complete_failed += 1
                    continue

            logger.info(
                f"[{self.neuraverse.account_index}] | Quests: {claimed_quests} claimed, {completed_quests} completed, {claim_failed} claim failed, {complete_failed} complete failed"
            )

            if claimed_quests > 0 or completed_quests > 0:
                return True
            else:
                return False

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Complete quests error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    @retry_async(default_value=None)
    async def get_all_quests(self) -> list:
        try:
            cookies = {
                "privy-token": self.neuraverse.privy_session_token,
                "privy-session": "privy.neuraprotocol.io",
                "privy-id-token": self.neuraverse.identity_token,
            }

            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5",
                "authorization": f"Bearer {self.neuraverse.identity_token}",
                "origin": "https://neuraverse.neuraprotocol.io",
                "priority": "u=1, i",
                "referer": "https://neuraverse.neuraprotocol.io/",
            }

            response = await self.neuraverse.session.get(
                "https://neuraverse-testnet.infra.neuraprotocol.io/api/tasks",
                cookies=cookies,
                headers=headers,
            )

            tasks = response.json().get("tasks", [])
            if not tasks:
                raise Exception(response.text)

            return tasks

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Get all leaderboard quests error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def complete_quest(self, quest: dict) -> bool:
        try:
            quest_id = quest.get("id")
            quest_name = quest.get("name")
            quest_points = quest.get("points")

            logger.info(
                f"[{self.neuraverse.account_index}] | Completing quest: {quest_name} ({quest_points} points)"
            )

            if quest_id == "collect_all_pulses":
                return await self.collect_all_pulses()

            elif quest_id == "daily_login":
                return True

            elif quest_id == "visit_all_map":
                return await self.visit_all_locations()

            elif quest_id == "claim_faucet":
                await self.visit_location("faucet:visit")
                return await self.faucet()

            else:
                raise Exception(f"Quest {quest_name} not supported yet")

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Complete quest error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def claim_quest(self, quest: dict) -> bool:
        try:
            quest_id = quest.get("id")
            quest_name = quest.get("name")

            logger.info(
                f"[{self.neuraverse.account_index}] | Claiming quest: {quest_name}"
            )

            cookies = {
                "privy-token": self.neuraverse.privy_session_token,
                "privy-session": "privy.neuraprotocol.io",
                "privy-id-token": self.neuraverse.identity_token,
            }

            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5",
                "authorization": f"Bearer {self.neuraverse.identity_token}",
                "content-type": None,
                "origin": "https://neuraverse.neuraprotocol.io",
                "priority": "u=1, i",
                "referer": "https://neuraverse.neuraprotocol.io/",
            }

            response = await self.neuraverse.session.post(
                f"https://neuraverse-testnet.infra.neuraprotocol.io/api/tasks/{quest_id}/claim",
                cookies=cookies,
                headers=headers,
                data=b"",
            )

            if "Task is not claimable" in response.text:
                logger.warning(
                    f"[{self.neuraverse.account_index}] | Quest {quest_name} is not claimable for now. Try again later."
                )
                return True

            response_json = response.json()
            status = response_json.get("status", None)
            points = response_json.get("points", None)

            if not status:
                raise Exception(response.text)

            if status != "claimed":
                raise Exception(response.text)

            logger.success(
                f"[{self.neuraverse.account_index}] | Claimed quest: {quest_name} ({points} points)"
            )
            return True
        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Claim quest error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def collect_all_pulses(self) -> bool:
        try:
            account_info = await self.neuraverse.get_account_info()
            if not account_info:
                raise Exception("unable to get account info")

            pulses_data = account_info.get("pulses", {})
            pulses = pulses_data.get("data", [])
            not_collected_pulses = [
                pulse for pulse in pulses if pulse.get("isCollected", None) is False
            ]

            pulse_ids = [
                pulse.get("id").replace("pulse:", "") for pulse in not_collected_pulses
            ]
            random.shuffle(pulse_ids)
            pulse_ids_logs = " ".join(pulse_ids)
            logger.info(
                f"[{self.neuraverse.account_index}] | Not collected pulses: [{pulse_ids_logs}]"
            )

            for pulse_id in pulse_ids:
                await self.collect_pulse(pulse_id)
                pause = random.randint(3, 5)
                logger.info(
                    f"[{self.neuraverse.account_index}] | Sleeping {pause} seconds before next pulse..."
                )
                await asyncio.sleep(pause)

            await asyncio.sleep(5)

            account_info = await self.neuraverse.get_account_info()
            if not account_info:
                raise Exception("unable to get account info")

            pulses_data = account_info.get("pulses", {})
            pulses = pulses_data.get("data", [])

            all_collected = all(pulse.get("isCollected", False) for pulse in pulses)
            if not all_collected:
                logger.error(
                    f"[{self.neuraverse.account_index}] | Not all pulses collected"
                )
                return False

            logger.success(
                f"[{self.neuraverse.account_index}] | All pulses collected successfully"
            )
            return True

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Collect all pulses error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    @retry_async(default_value=False)
    async def collect_pulse(self, pulse_id: str) -> bool:
        try:
            cookies = {
                "privy-session": "privy.neuraprotocol.io",
                "privy-token": self.neuraverse.privy_session_token,
                "privy-id-token": self.neuraverse.identity_token,
            }

            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5",
                "authorization": f"Bearer {self.neuraverse.identity_token}",
                "content-type": "application/json",
                "origin": "https://neuraverse.neuraprotocol.io",
                "priority": "u=1, i",
                "referer": "https://neuraverse.neuraprotocol.io/",
            }

            json_data = {
                "type": "pulse:collectPulse",
                "payload": {
                    "id": "pulse:" + pulse_id,
                },
            }

            response = await self.neuraverse.session.post(
                "https://neuraverse-testnet.infra.neuraprotocol.io/api/events",
                cookies=cookies,
                headers=headers,
                json=json_data,
            )
            if (
                response.status_code > 199
                and response.status_code < 300
                and "pulse:collectPulse" in response.text
            ):
                logger.success(
                    f"[{self.neuraverse.account_index}] | Collected pulse {pulse_id} successfully"
                )
                return True
            else:
                raise Exception(response.text)

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Collect pulse {pulse_id} error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def visit_all_locations(self) -> bool:
        try:
            locations = SUPPORTED_GAME_VISIT_LOCATIONS_IDS
            random.shuffle(locations)

            for location in locations:
                await self.visit_location(location)
                pause = random.randint(3, 6)
                logger.info(
                    f"[{self.neuraverse.account_index}] | Sleeping {pause} seconds before next location..."
                )
                await asyncio.sleep(pause)

            return True
        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Visit all locations error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            return False

    @retry_async(default_value=False)
    async def visit_location(self, location_id: str) -> bool:
        try:
            cookies = {
                "privy-session": "privy.neuraprotocol.io",
                "privy-token": self.neuraverse.privy_session_token,
                "privy-id-token": self.neuraverse.identity_token,
            }

            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5",
                "authorization": f"Bearer {self.neuraverse.identity_token}",
                "content-type": "application/json",
                "origin": "https://neuraverse.neuraprotocol.io",
                "referer": "https://neuraverse.neuraprotocol.io/",
            }

            json_data = {
                "type": f"{location_id}",
            }

            response = await self.neuraverse.session.post(
                "https://neuraverse-testnet.infra.neuraprotocol.io/api/events",
                cookies=cookies,
                headers=headers,
                json=json_data,
            )

            if (
                response.status_code > 199
                and response.status_code < 300
                and f"{location_id}" in response.text
            ):
                logger.success(
                    f"[{self.neuraverse.account_index}] | Visited location {location_id} successfully"
                )
                return True
            else:
                raise Exception(response.text)

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"[{self.neuraverse.account_index}] | Visit location {location_id} error: {e}. Sleeping {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def faucet(self) -> bool:
        try:
            logger.error(f"[{self.neuraverse.account_index}] | Faucet does not work for now. Let me know in Starlabs chat when the faucet starts working.")
            return False
            
            cookies = {
                "privy-token": self.neuraverse.privy_session_token,
                "privy-session": "privy.neuraprotocol.io",
                "privy-id-token": self.neuraverse.identity_token,
            }

            headers = {
                "accept": "text/x-component",
                "accept-language": "en-US,en;q=0.9,ru;q=0.8,zh-TW;q=0.7,zh;q=0.6,uk;q=0.5",
                "content-type": "text/plain;charset=UTF-8",
                "next-action": "78d30d59c8b72e2764652e54a911a68b75852982b3",
                "next-router-state-tree": "%5B%22%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%2Cnull%2Cnull%5D%7D%2Cnull%2Cnull%2Ctrue%5D",
                "origin": "https://neuraverse.neuraprotocol.io",
                "priority": "u=1, i",
                "referer": "https://neuraverse.neuraprotocol.io/?section=faucet",
            }

            params = {
                "section": "faucet",
            }

            data = (
                '["'
                + self.neuraverse.wallet.address
                + '",267,"'
                + self.neuraverse.identity_token
                + '",true]'
            )

            response = await self.neuraverse.session.post(
                "https://neuraverse.neuraprotocol.io/",
                params=params,
                cookies=cookies,
                headers=headers,
                data=data,
            )

            if "Insufficient neuraPoints." in response.text:
                message = response.text.split("Insufficient neuraPoints.")[1].split('"')[0].strip()
                logger.error(
                    f"[{self.neuraverse.account_index}] | Insufficient neuraPoints: {message}"
                )
                return False
            
            if "Address has already received" in response.text:
                logger.success(
                    f"[{self.neuraverse.account_index}] | Address has already received faucet"
                )
                return True
            
            if "ANKR distribution successful" in response.text:
                logger.success(
                    f"[{self.neuraverse.account_index}] | Faucet claimed successfully"
                )
                
                try:
                    event_headers = {
                        "accept": "application/json, text/plain, */*",
                        "authorization": f"Bearer {self.neuraverse.identity_token}",
                        "content-type": "application/json",
                        "origin": "https://neuraverse.neuraprotocol.io",
                        "referer": "https://neuraverse.neuraprotocol.io/",
                    }
                    await self.neuraverse.session.post(
                        "https://neuraverse-testnet.infra.neuraprotocol.io/api/events",
                        cookies=cookies,
                        headers=event_headers,
                        json={"type": "faucet:claimTokens"}
                    )
                    logger.info(f"[{self.neuraverse.account_index}] | Faucet event sent")
                except Exception as event_error:
                    logger.warning(f"[{self.neuraverse.account_index}] | Failed to send faucet event: {event_error}")
                
                return True
            else:
                raise Exception(response.text)

        except Exception as e:
            random_pause = random.randint(
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.neuraverse.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            if "Operation timed out after" in str(e):
                pass
            else:
                logger.error(
                    f"[{self.neuraverse.account_index}] | Faucet error: {e}. Sleeping {random_pause} seconds..."
                )
            await asyncio.sleep(random_pause)
            raise
