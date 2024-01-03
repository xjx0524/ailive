# -*- coding: utf-8 -*-
import logging
from typing import *
import multiprocessing as mp
import blivedm
import blivedm.models.web as web_models

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("LiveHandler")

class InteractWordMessage:
    def __init__(self, uname):
        self._uname = uname
    
    @property
    def uname(self):
        return self._uname

class LiveHandler(blivedm.BaseHandler):

    def __init__(self, queue: mp.Queue):
        self.queue = queue

    # 演示如何添加自定义回调
    _CMD_CALLBACK_DICT = blivedm.BaseHandler._CMD_CALLBACK_DICT.copy()
    
    # 入场消息回调
    def __interact_word_callback(self, client: blivedm.BLiveClient, command: dict):
        logger.info(f"[{client.room_id}] INTERACT_WORD: self_type={type(self).__name__}, room_id={client.room_id},"
              f" uname={command['data']['uname']}")
        msg = InteractWordMessage(command['data']['uname'])
        self.queue.put_nowait(msg)
    _CMD_CALLBACK_DICT['INTERACT_WORD'] = __interact_word_callback

    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        logger.info(f'[{client.room_id}] 心跳')

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        logger.info(f'[{client.room_id}] {message.uname}：{message.msg}')
        self.queue.put_nowait(message)

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        logger.info(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
              f' （{message.coin_type}瓜子x{message.total_coin}）')
        self.queue.put_nowait(message)

    def _on_buy_guard(self, client: blivedm.BLiveClient, message: web_models.GuardBuyMessage):
        logger.info(f'[{client.room_id}] {message.username} 购买{message.gift_name}')

    def _on_super_chat(self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage):
        logger.info(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')
        self.queue.put_nowait(message)