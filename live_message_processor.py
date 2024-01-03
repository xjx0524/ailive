# -*- coding: utf-8 -*-
import time
from datetime import datetime
import logging
import queue
import multiprocessing as mp
from typing import *
from live_handler import InteractWordMessage
import blivedm.models.web as web_models
import ai_utils

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("MsgProcessor")

current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"logs/app_{current_time}.log"

# 创建一个用于写入日志文件的处理器
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setLevel(logging.INFO)  # 设置文件处理器的日志级别

# 创建一个用于输出到控制台的处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # 设置控制台处理器的日志级别

# 定义日志格式
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 将处理器添加到记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class LiveMessageProcess(mp.Process):
    def __init__(self, queue: mp.Queue):
        super().__init__()
        self.queue = queue
        self.chat_history = []
        self.chat_max_size = 100
        self.cold_time_ts = time.time()
        self.cold_time_gap = 30

    def run(self):
        while True:
            try:
                message = self.queue.get_nowait()
                # logger.info(type(message))
                if message is None:
                    logger.info("exit by None!")
                    break  # 使用 None 作为停止信号
                if type(message) == web_models.DanmakuMessage:
                    query = f'{message.uname}说：{message.msg}'
                    ans = ai_utils.chat(query, self.chat_history)
                    logger.info(f'[chat]{query}_|_{ans}')
                    self.chat_history.append([query, ans])
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                elif type(message) == InteractWordMessage:
                    ans = f'欢迎{message.uname}进入直播间，哈哈，你真是好眼光啊！'
                    logger.info(f'[say]{ans}')
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                elif type(message) == web_models.GiftMessage:
                    ans = f'感谢老板赠送的{message.num}个{message.gift_name}，您就是我的衣食父母！'
                    logger.info(f'[say]{ans}')
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                elif type(message) == web_models.SuperChatMessage:
                    query = f'{message.uname}说：{message.message}'
                    ans = ai_utils.chat(query, self.chat_history)
                    logger.info(f'[chat]{query}_|_{ans}')
                    self.chat_history.append([query, ans])
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                else:
                    pass
                ai_utils.reset_captions()
                if len(self.chat_history) > self.chat_max_size:
                    self.chat_history = self.chat_history[-self.chat_max_size:]
                self.cold_time_ts = time.time()
            except queue.Empty:
                if time.time() - self.cold_time_ts >= self.cold_time_gap:
                    query = '没人说话，你随便说点啥'
                    ans = ai_utils.chat(query, self.chat_history)
                    logger.info(f'[chat]{query}_|_{ans}')
                    # self.chat_history.append([query, ans])
                    ai_utils.captions(ans)
                    ai_utils.tts_and_play(ans)
                    self.cold_time_ts = time.time()
                    ai_utils.reset_captions()


class LiveEntryProcess(mp.Process):
    def __init__(self, queue: mp.Queue, qout: mp.Queue):
        super().__init__()
        self.queue = queue
        self.qout = qout
        self.chat_history = []
        self.chat_max_size = 100
        self.cold_time_ts = time.time()
        self.cold_time_gap = 90

    def run(self):
        logger.info(str(self.__class__) + ' start.')
        while True:
            try:
                message = self.queue.get_nowait()
                # logger.info(type(message))
                if message is None:
                    logger.info("exit by None!")
                    break  # 使用 None 作为停止信号
                if type(message) == web_models.DanmakuMessage:
                    query = f'{message.uname}说：{message.msg}'
                    self.qout.put_nowait((query, self.chat_history, True))
                elif type(message) == InteractWordMessage:
                    ans = f'欢迎{message.uname}进入直播间，哈哈，你真是好眼光啊！'
                    self.qout.put_nowait((ans, self.chat_history, False))
                elif type(message) == web_models.GiftMessage:
                    ans = f'感谢老板赠送的{message.num}个{message.gift_name}，您就是我的衣食父母！'
                    self.qout.put_nowait((ans, self.chat_history, False))
                elif type(message) == web_models.SuperChatMessage:
                    query = f'{message.uname}说：{message.message}'
                    self.qout.put_nowait((query, self.chat_history, True))
                else:
                    pass
                if len(self.chat_history) > self.chat_max_size:
                    self.chat_history = self.chat_history[-self.chat_max_size:]
                self.cold_time_ts = time.time()
            except queue.Empty:
                if time.time() - self.cold_time_ts >= self.cold_time_gap:
                    query = '没人说话，你随便说点啥'
                    self.qout.put_nowait((query, self.chat_history, True))
                    self.cold_time_ts = time.time()
            except Exception as e:
                print(e)


class ChatProcess(mp.Process):
    def __init__(self, queue: mp.Queue, qout: mp.Queue):
        super().__init__()
        self.queue = queue
        self.qout = qout

    def run(self):
        logger.info(str(self.__class__) + ' start.')
        while True:
            try:
                message = self.queue.get()
                if message is None:
                    logger.info("exit by None!")
                    self.qout.put_nowait(None)
                    break  # 使用 None 作为停止信号
                query, history, needAnswer = message
                if needAnswer:
                    ans = ai_utils.chat(query, history)
                    logger.info(f'[chat]{query}_|_{ans}')
                else:
                    ans = query
                    logger.info(f'[say]{ans}')
                self.qout.put(ans)
            except Exception as e:
                logger.error(e)


class TTSProcess(mp.Process):
    def __init__(self, queue: mp.Queue, qout: mp.Queue):
        super().__init__()
        self.queue = queue
        self.qout = qout

    def run(self):
        logger.info(str(self.__class__) + ' start.')
        while True:
            try:
                message = self.queue.get()
                if message is None:
                    logger.info("exit by None!")
                    break  # 使用 None 作为停止信号
                sr, audio = ai_utils.tts(message)
                self.qout.put_nowait((message, sr, audio))
            except Exception as e:
                logger.error(e)


class PlaySoundProcess(mp.Process):
    def __init__(self, queue: mp.Queue):
        super().__init__()
        self.queue = queue

    def run(self):
        logger.info(str(self.__class__) + ' start.')
        while True:
            try:
                message = self.queue.get()
                if message is None:
                    logger.info("exit by None!")
                    break  # 使用 None 作为停止信号
                ans, sample_rate, audio = message
                ai_utils.captions(ans)
                ai_utils.play_sound(audio, sample_rate)
                ai_utils.reset_captions()
            except Exception as e:
                logger.error(e)


class QueueMonitorProcess(mp.Process):
    def __init__(self, queue_map: Dict[str, mp.Queue]):
        super().__init__()
        self.queue_map = queue_map
        self.log_time = 30

    def run(self):
        logger.info(str(self.__class__) + ' start.')
        while True:
            msg = 'queue size monitor: '
            msg += '\t'.join([qname+'_'+str(q.qsize()) for qname, q in self.queue_map.items()])
            logger.info(msg)
            time.sleep(self.log_time)
