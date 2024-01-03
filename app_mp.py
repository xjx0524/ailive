# -*- coding: utf-8 -*-
import asyncio
import http.cookies
from typing import *
import time
from datetime import datetime
import aiohttp
import logging
import multiprocessing as mp

import blivedm
import ai_utils
from live_handler import LiveHandler
from live_message_processor import *


logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# b站cookie里的sessdata
SESSDATA = ''
# 监听房间号
my_room_id = 743021
session: Optional[aiohttp.ClientSession] = None

async def main(message_queue):
    init_session()
    try:
        await run_single_client(message_queue)
    finally:
        await session.close()

def init_session():
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)
    logger.info('dmclient init done.')

async def run_single_client(message_queue):
    """
    演示监听一个直播间
    """
    room_id = my_room_id
    client = blivedm.BLiveClient(room_id, session=session)
    handler = LiveHandler(message_queue)
    client.set_handler(handler)

    client.start()
    logger.info('dmclient start.')
    logger.info('handler message queue start.')
    try:
        await client.join()
    finally:
        message_queue.put_nowait(None)
        await client.stop_and_close()



if __name__ == '__main__':
    logger.info('main init done.')

    # message_queue = mp.Queue()

    # p = LiveMessageProcess(message_queue)
    # p.start()

    message_queue = mp.Queue()
    queue_map = {
        'entry': message_queue,
        'chat': mp.Queue(),
        'tts': mp.Queue(),
        'play': mp.Queue()
    }
    process_list = []
    process_list.append(LiveEntryProcess(queue_map['entry'], queue_map['chat']))
    process_list.append(ChatProcess(queue_map['chat'], queue_map['tts']))
    # process_list.append(ChatProcess(queue_map['chat'], queue_map['tts']))
    # process_list.append(TTSProcess(queue_map['tts'], queue_map['play']))
    process_list.append(TTSProcess(queue_map['tts'], queue_map['play']))
    process_list.append(PlaySoundProcess(queue_map['play']))
    process_list.append(QueueMonitorProcess(queue_map))

    for p in process_list:
        p.start()

    ai_utils.tts_and_play('原神！启动！')

    asyncio.run(main(message_queue))

    # p.join()

    for p in process_list:
        p.join()
