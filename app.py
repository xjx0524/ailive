# -*- coding: utf-8 -*-
import asyncio
import http.cookies
from typing import *
import time
from datetime import datetime
import aiohttp
import logging

import blivedm
import blivedm.models.web as web_models
import ai_utils

logging.getLogger("blivedm").setLevel(logging.WARNING)

logging.basicConfig(
    level=logging.INFO, format="| %(name)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"logs/app_{current_time}.log"

# 创建一个用于写入日志文件的处理器
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.INFO)  # 设置文件处理器的日志级别

# 创建一个用于输出到控制台的处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # 设置控制台处理器的日志级别

# 定义日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 将处理器添加到记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)
# class logger:
#     def info(s):
#         print(s)


wav_file_path = "output/wav_file"
SESSDATA = '30dc5af4%2C1719413230%2C96477%2Ac1CjBvXciNRV8M68Bzn9_cTUUvW68qdUbBz0dE3UHl5u4eBhZ3fjg3HdgtRuG5QxYwyAUSVm1YTVp2anpSdTdGcWxGcHpaYzROeFpNZFh1dExfTkp1S3JOcmJQbDNXM1d4Q0VhQWVDN1JyT0lsc003M0dOdjRUVm5Zbzh5WmNyelgzQkRDdThaaldBIIEC'
# SESSDATA = None
my_room_id = 743021
session: Optional[aiohttp.ClientSession] = None

async def main():
    init_session()
    try:
        await run_single_client()
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

async def run_single_client():
    """
    演示监听一个直播间
    """
    room_id = my_room_id
    client = blivedm.BLiveClient(room_id, session=session)
    handler = MyHandler()
    client.set_handler(handler)

    client.start()
    logger.info('dmclient start.')
    message_queue_task = asyncio.create_task(handler.process_message_queue())
    logger.info('handler message queue start.')
    try:
        await client.join()
    finally:
        message_queue_task.cancel()
        await client.stop_and_close()

class MyHandler(blivedm.BaseHandler):

    def __init__(self):
        self.dm_queue = asyncio.Queue()
        self.sc_queue = asyncio.Queue()
        self.gift_queue = asyncio.Queue()
        self.room_queue = asyncio.Queue()
        self.chat_history = []
        self.chat_max_size = 100
        self.cold_time_ts = time.time()
        self.cold_time_gap = 30
    
    async def process_message_queue(self):
        while True:
            try:
                if len(self.chat_history) > self.chat_max_size:
                    self.chat_history = self.chat_history[-self.chat_max_size:]
                # print([time.time(), self.dm_queue.qsize(), self.room_queue.qsize(), self.sc_queue.qsize(), self.gift_queue.qsize()])
                if not self.gift_queue.empty():
                    message = await self.gift_queue.get()
                    ans = f'感谢老板赠送的{message.num}个{message.gift_name}，您就是我的衣食父母！'
                    logger.info(f'[say]{ans}')
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                    self.cold_time_ts = time.time()
                    self.gift_queue.task_done()
                elif not self.sc_queue.empty():
                    message = await self.sc_queue.get()
                    query = f'{message.uname}说：{message.message}'
                    ans = ai_utils.chat(query, self.chat_history)
                    logger.info(f'[chat]{query}_|_{ans}')
                    self.chat_history.append([query, ans])
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                    self.cold_time_ts = time.time()
                    self.sc_queue.task_done()
                elif not self.room_queue.empty():
                    uname = await self.gift_queue.get()
                    print(uname)
                    ans = f'欢迎{uname}进入直播间，哈哈，你真是好眼光啊！'
                    logger.info(f'[say]{ans}')
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                    self.cold_time_ts = time.time()
                    self.room_queue.task_done()
                elif not self.dm_queue.empty():
                    message = await self.dm_queue.get()
                    query = f'{message.uname}说：{message.msg}'
                    ans = ai_utils.chat(query, self.chat_history)
                    logger.info(f'[chat]{query}_|_{ans}')
                    self.chat_history.append([query, ans])
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                    self.cold_time_ts = time.time()
                    self.dm_queue.task_done()
                else:
                    if time.time() - self.cold_time_ts >= self.cold_time_gap:
                        query = '没人说话，你随便说点啥'
                        ans = ai_utils.chat(query, self.chat_history)
                        logger.info(f'[chat]{query}_|_{ans}')
                        # self.chat_history.append([query, ans])
                        ai_utils.captions(ans)
                        ai_utils.tts_and_play(ans)
                        self.cold_time_ts = time.time()
                    await asyncio.sleep(0)
                ai_utils.reset_captions()
            except Exception as e:
                print(e)

    # # 演示如何添加自定义回调
    # _CMD_CALLBACK_DICT = blivedm.BaseHandler._CMD_CALLBACK_DICT.copy()
    
    # # 入场消息回调
    # def __interact_word_callback(self, client: blivedm.BLiveClient, command: dict):
    #     logger.info(f"[{client.room_id}] INTERACT_WORD: self_type={type(self).__name__}, room_id={client.room_id},"
    #           f" uname={command['data']['uname']}")
    #     self.room_queue.put_nowait(command['data']['uname'])
    # _CMD_CALLBACK_DICT['INTERACT_WORD'] = __interact_word_callback  # noqa

    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        logger.info(f'[{client.room_id}] 心跳')

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        logger.info(f'[{client.room_id}] {message.uname}：{message.msg}')
        self.dm_queue.put_nowait(message)

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        logger.info(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
              f' （{message.coin_type}瓜子x{message.total_coin}）')
        self.gift_queue.put_nowait(message)

    def _on_buy_guard(self, client: blivedm.BLiveClient, message: web_models.GuardBuyMessage):
        logger.info(f'[{client.room_id}] {message.username} 购买{message.gift_name}')

    def _on_super_chat(self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage):
        logger.info(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')
        self.sc_queue.put_nowait(message)

if __name__ == '__main__':
    logger.info('main init done.')

    ai_utils.tts_and_play('原神！启动！')

    asyncio.run(main())
