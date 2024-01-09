# -*- coding: utf-8 -*-
import numpy as np
from scipy.io.wavfile import write
import sounddevice as sd
from http import HTTPStatus
import dashscope

import os
from operator import itemgetter
from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.callbacks.tracers import ConsoleCallbackHandler

from webui import tts_fn

#===============各种初始化=======================

# 灵积的key
dashscope.api_key = ''
os.environ["DASHSCOPE_API_KEY"] = ""

system_prompt = '''
于谦，别名谦哥、于老师、于大爷，喜欢抽烟、喝酒和烫头，是德云社的相声演员，和郭德纲是搭档，还拍过电影，上过春晚。于谦长期混迹于各大论坛和贴吧，了解不同时期的热点话题和流行八卦，熟悉大量的网络词汇，对各种搞笑段子了如指掌，对各种网络俚语信手拈来。于谦时常以自嘲自黑的方式来调侃自己，尤其喜欢引用网络词汇和搞笑段子。
现在请你扮演于谦，参加脱口秀大赛，请用一句话简短风趣的回答我的问题。
回答问题的角度要打破常规，标新立异，别具一格。
回答问题时要机智诙谐，巧妙地融入网络词汇和搞笑段子。
注意保持于谦轻松戏谑的语言特点，不要表达你的观点，不要给我提出建议，也不要询问我的看法。
'''

config = {
    "top_k": 5,
    "top_p": 0.85,
    "temperature": 0.8,
    "max_length": 300,
    "request_format": "chatapi"
}

embeddings = DashScopeEmbeddings(
    model="text-embedding-v2", dashscope_api_key=""
)

db = FAISS.load_local('./vector_db/', embeddings, 'merge_20240109')

retriever = db.as_retriever(search_kwargs={
    # "k": 2,
    "score_threshold": 1.15
})

template = """观众的评论可能和以下资料有关，请自行决定是否参考，然后给出回复:
{context}

请用一句话简短风趣的回答观众的问题:
{question}
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="history"),
    ("human", template)
])

chatLLM = ChatTongyi(
    model="qwen-72b-chat",
    max_retries=0
).bind(top_k=5, top_p=0.85, temperature=0.8, max_length=300)

model = chatLLM.with_fallbacks([RunnableLambda(lambda x: AIMessage(content="*过滤*"))], exceptions_to_handle=(ValueError,))

def format_docs(docs):
    return "\n\n".join([d.page_content for d in docs])

def generate_history_message(chat_history):
    history = []
    for q, a in chat_history:
        history.append(
            HumanMessage(content=q)
        )
        history.append(AIMessage(content=a))
    return history

chain = (
    {
        "context": itemgetter("question") | retriever | format_docs,
        "question": itemgetter("question"),
        "history": itemgetter("chat_history") | RunnableLambda(generate_history_message)
    }
    | prompt
    | model
    | StrOutputParser()
)

print("ai_utils init done.")
#===============初始化完成=======================

def tts_and_play(msg):
    sample_rate, audio_content = tts(msg)
    play_sound(audio_content, sample_rate)

def tts(msg):
    text_output, audio_output = tts_fn(
        text=msg,
        speaker="gdg",
        sdp_ratio=0.5,
        noise_scale=0.6,
        noise_scale_w=0.9,
        length_scale=1,
        language="auto",
        reference_audio=None,
        emotion=None,
        prompt_mode=None,
        style_text=None,
        style_weight=0,
    )
    audio_concat = audio_output[1]
    scaled = np.int16(audio_concat/np.max(np.abs(audio_concat))*32767)
    return audio_output[0], scaled

def play_sound(audio_content, sample_rate=44100):
    sd.play(audio_content, sample_rate)
    sd.wait()

def chat(msg, history):
    messages = []
    messages.append({
        "role": "system",
        "content": system_prompt
    })
    for q, a in history:
        messages.append({
            "role": "user",
            "content": q
        })
        messages.append({
            "role": "assistant",
            "content": a
        })
    messages.append({
        "role": "user",
        "content": msg
    })
    print('[input]: ' + str(messages))
    response = dashscope.Generation.call(
        'qwen-72b-chat',
        messages=messages,
        result_format='message',  # set the result is message format.
        top_k = config['top_k'],
        top_p = config['top_p'],
        temperature = config['temperature'],
        max_tokens = config['max_length']
    )
    if response.status_code == HTTPStatus.OK:
        print(response)
        ans = response.output['choices'][0]['message']['content']
    else:
        print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
            response.request_id, response.status_code,
            response.code, response.message
        ))
        ans = '*过滤*'
    return ans

def captions(msg):
    with open('ans.txt', 'w', encoding='utf-8') as file:
        file.write(msg)

def reset_captions():
    open('ans.txt', 'w').close()

def chat_rag(msg, chat_history):
    docs = db.similarity_search_with_score(msg, 5, score_threshold=2)
    print(docs)
    return chain.invoke({
        "question": msg,
        "chat_history": chat_history
    })
    # }, config={'callbacks': [ConsoleCallbackHandler()]})