"""
NexSandglass 情绪词库 — 动态学习
================================
初始内置词库 + 随用户使用自动扩展。
与画像层联动：画像里的偏好/禁区帮助理解情绪。
"""

import json, os
from datetime import datetime

_VOCAB_FILE = os.path.join(os.path.expanduser("~"), ".neurobase", "emotion_vocab.json")

# ── 内置初始词库（中英双语）──
_BUILTIN = {
    "红牌": {
        "zh": ["不管了", "随便", "放弃", "能用就行", "不纠结了", "就这样吧"],
        "en": ["whatever", "give up", "i don't care", "fine, do what you want"],
    },
    "负面": {
        "zh": ["烦死了", "好累", "压力好大", "真受不了", "没意思", "无聊透顶", "失望",
              "我好焦虑", "不想干了", "太难受了", "崩溃", "不开心", "还是这样", "算了"],
        "en": ["frustrated", "exhausted", "stressed out", "sick of this",
              "disappointed", "anxious", "sad", "tired of"],
    },
    "困惑": {
        "zh": ["不懂", "不明白", "怎么回事", "啥意思", "搞不懂", "奇怪", "不对劲"],
        "en": ["confused", "don't understand", "what's going on", "doesn't make sense"],
    },
    "积极": {
        "zh": ["开心", "太好了", "有意思", "满意", "值得", "期待", "兴奋", "好棒"],
        "en": ["happy", "great", "excited", "awesome", "love it", "worth it"],
    },
}

# ── 主语标记（判断情绪来源）──
_SUBJECT_OTHERS = ["他", "她", "他们", "那个人", "别人", "he ", "she ", "they ", "that person", "someone"]
_SUBJECT_IMPACT = ["他让", "她让", "他们让", "害得", "he makes", "she makes", "they make"]


def load_vocab() -> dict:
    """加载情绪词库。首次使用从内置词库初始化。"""
    if os.path.exists(_VOCAB_FILE):
        try:
            with open(_VOCAB_FILE, "r", encoding="utf-8") as f:
                vocab = json.loads(f.read())
            # 合并内置词库（确保内置词不丢失）
            for mood, langs in _BUILTIN.items():
                if mood not in vocab:
                    vocab[mood] = {}
                for lang, words in langs.items():
                    existing = set(vocab[mood].get(lang, []))
                    existing.update(words)
                    vocab[mood][lang] = sorted(existing)
            return vocab
        except Exception:
            pass

    # 首次初始化
    vocab = {mood: {lang: sorted(words) for lang, words in langs.items()}
             for mood, langs in _BUILTIN.items()}
    save_vocab(vocab)
    return vocab


def save_vocab(vocab: dict):
    """保存情绪词库到本地。"""
    os.makedirs(os.path.dirname(_VOCAB_FILE), exist_ok=True)
    with open(_VOCAB_FILE, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)


def learn(word: str, mood: str, lang: str = "zh"):
    """学习新情绪词。用户表达了一个新的情绪词，收录进词库。"""
    vocab = load_vocab()
    if mood not in vocab:
        vocab[mood] = {}
    if lang not in vocab[mood]:
        vocab[mood][lang] = []

    if word not in vocab[mood][lang]:
        vocab[mood][lang].append(word)
        vocab[mood][lang] = sorted(vocab[mood][lang])
        save_vocab(vocab)
        return True
    return False


def detect(message: str) -> dict:
    """检测一条消息的情绪。返回 {mood, emitter, keywords}。"""
    vocab = load_vocab()
    msg_lower = message.lower()

    for mood in ["红牌", "负面", "困惑", "积极"]:
        all_words = vocab.get(mood, {}).get("zh", []) + vocab.get(mood, {}).get("en", [])
        for word in sorted(all_words, key=len, reverse=True):  # 长词优先
            if word.lower() in msg_lower:
                idx = msg_lower.find(word.lower())
                ctx = message[max(0, idx-30):idx].lower()

                # 主语判断
                if any(w in ctx for w in _SUBJECT_OTHERS):
                    emitter = "他人"
                elif any(w in ctx for w in _SUBJECT_IMPACT):
                    emitter = "影响"
                else:
                    emitter = "自我"

                # 把新表达方式加入学习候选
                # （如果是"负面"且emitter="自我"，这条消息可能包含新情绪词）
                if emitter == "自我" and mood in ["负面", "积极"]:
                    # 提取可能的情绪词（2-4字中文词）
                    import re
                    candidates = re.findall(r"[\u4e00-\u9fff]{2,4}", message)
                    for c in candidates:
                        if c not in all_words and len(c) >= 2:
                            # 标记为候选——下次确认后正式收录
                            pass

                return {"mood": mood, "emitter": emitter, "keywords": [word]}

    return {"mood": "", "emitter": "自我", "keywords": []}


def mood_message(detection: dict) -> str:
    """根据检测结果生成管家消息。"""
    mood = detection["mood"]
    emitter = detection["emitter"]
    words = detection["keywords"][:2]

    if not mood:
        return ""

    msgs = {
        ("红牌", "自我"): f"🔴 觉察：红牌信号——「{'、'.join(words)}」。优先级=自我修正。",
        ("负面", "自我"): f"🟡 觉察：你看起来状态不太好——「{'、'.join(words)}」",
        ("负面", "他人"): f"🟡 觉察：别人状态不太好——「{'、'.join(words)}」。不影响你的提醒。",
        ("负面", "影响"): f"🟡 觉察：别人的情绪影响到你了——「{'、'.join(words)}」。提醒先缓一缓。",
        ("困惑", "自我"): f"🟡 觉察：你好像有点困惑——「{'、'.join(words)}」",
        ("积极", "自我"): f"🟢 觉察：状态不错——「{'、'.join(words)}」",
        ("积极", "他人"): f"🟢 觉察：别人状态不错——「{'、'.join(words)}」",
    }
    return msgs.get((mood, emitter), "")
