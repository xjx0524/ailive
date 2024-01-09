import time
from datetime import datetime
import logging
import multiprocessing as mp
from types import SimpleNamespace

import ai_utils
from live_message_processor import *
import comment_api
from live_message_type import LiveMessageType


logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


topic = "dd49cc3c-53db-46c9-a44e-66bd5d8b399f"

def listen_message(qout):
    msg_history = comment_api.get_comments(topic)
    msg_history.sort(key=lambda c: c.timestamp)
    msg_queue_size = 100
    while True:
        if len(msg_history) > msg_queue_size:
            msg_history = msg_history[-msg_queue_size:]
        comments = comment_api.get_comments(topic)
        comments.sort(key=lambda c: c.timestamp)
        msg_history_set = set([c.commentId for c in msg_history])

        num_new_msg = 0
        for comment in comments:
            if comment.commentId in msg_history_set:
                continue
            print(comment)
            msg_history.append(comment)
            num_new_msg += 1
            if comment.enhancedType is not None and comment.enhancedType.lower() == 'follow':
                qout.put((LiveMessageType.FOLLOW, SimpleNamespace(nickname=comment.publisherNick)))
            else:
                qout.put((LiveMessageType.COMMENT, SimpleNamespace(nickname=comment.publisherNick, message=comment.content)))
        if num_new_msg < 3:
            time.sleep(3 - num_new_msg)


if __name__ == "__main__":
    message_queue = mp.Queue()
    queue_map = {
        'entry': message_queue,
        'chat': mp.Queue(),
        'tts': mp.Queue(),
        'play': mp.Queue()
    }
    process_list = []
    process_list.append(LiveEntryCommonProcess(queue_map['entry'], queue_map['chat']))
    process_list.append(ChatProcess(queue_map['chat'], queue_map['tts']))
    # process_list.append(ChatProcess(queue_map['chat'], queue_map['tts']))
    # process_list.append(TTSProcess(queue_map['tts'], queue_map['play']))
    process_list.append(TTSProcess(queue_map['tts'], queue_map['play']))
    process_list.append(PlaySoundProcess(queue_map['play']))
    process_list.append(QueueMonitorProcess(queue_map))

    for p in process_list:
        p.start()

    ai_utils.tts_and_play('原神！启动！')

    listen_message(message_queue)

    for p in process_list:
        p.join()