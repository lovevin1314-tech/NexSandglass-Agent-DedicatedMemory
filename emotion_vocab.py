"""
NexSandglass 情绪词库 — 七大情绪分类
=====================================
基于 Ekman + Plutchik 情绪理论。
动态学习 + 主语判断 + 管家回应策略。
"""

import json, os, re

_VOCAB_FILE = os.path.join(os.path.expanduser("~"), ".neurobase", "emotion_vocab.json")

# ── 七大情绪分类 ──
# 格式：{大类: {子类: [词], 管家策略: "xxx"}}
_BUILTIN = {
    "愤怒": {
        "zh": ["气死", "恼火", "凭什么", "不公平", "过分", "太气人了", "火大", "无语",
              "受不了", "真恶心", "怎么这样", "太糟糕了"],
        "en": ["angry", "pissed off", "outrageous", "unfair", "ridiculous", "unacceptable"],
        "策略": "缓提醒。先让情绪降下来，不提待办。",
        "优先级": "高",
    },
    "悲伤": {
        "zh": ["难过", "伤心", "好累", "不想动", "心累", "崩溃", "失望",
              "没劲", "没意思", "提不起劲", "好难过"],
        "en": ["sad", "depressed", "heartbroken", "disappointed", "exhausted", "drained"],
        "策略": "缓提醒。状态不好的时候不催。",
        "优先级": "高",
    },
    "焦虑": {
        "zh": ["焦虑", "紧张", "压力好大", "害怕", "不安", "担心",
              "怎么办", "万一", "会不会", "好怕"],
        "en": ["anxious", "nervous", "stressed", "worried", "afraid", "scared"],
        "策略": "不催。给安全感，不提额外负担。",
        "优先级": "中",
    },
    "放弃": {
        "zh": ["不管了", "随便", "放弃", "就这样吧", "不做了", "算了算了",
              "不纠结了", "爱咋咋地", "无所谓", "能用就行"],
        "en": ["whatever", "give up", "i don't care", "fine, do what you want", "i quit"],
        "策略": "红牌。提醒全停，优先级=自我修正。",
        "优先级": "最高",
    },
    "开心": {
        "zh": ["开心", "太好了", "满意", "有意思", "值得", "兴奋", "好棒",
              "哈哈", "nice", "真不错", "有成就感", "爽", "喜欢"],
        "en": ["happy", "great", "excited", "awesome", "love it", "worth it", "amazing"],
        "策略": "正常提醒。状态好可以多提醒。",
        "优先级": "低",
    },
    "困惑": {
        "zh": ["不懂", "不明白", "怎么回事", "啥意思", "搞不懂", "奇怪",
              "不对劲", "不太对", "有点奇怪", "没搞明白"],
        "en": ["confused", "don't understand", "what's going on", "doesn't make sense"],
        "策略": "正常。帮助澄清，不影响提醒。",
        "优先级": "低",
    },
    "意外": {
        "zh": ["没想到", "竟然", "不是吧", "真的假的", "天哪",
              "怎么回事这样", "原来是"],
        "en": ["wow", "unexpected", "surprised", "really", "no way", "oh my"],
        "策略": "正常。分享惊喜，不影响提醒。",
        "优先级": "低",
    },
}

# ── 主语标记 ──
_SUBJECT_OTHERS = ["他", "她", "他们", "那个人", "别人",
                   "he ", "she ", "they ", "that person", "someone"]
_SUBJECT_IMPACT = ["他让", "她让", "他们让", "害得",
                   "he makes", "she makes", "they make"]


def load_vocab() -> dict:
    """加载情绪词库。合并内置词库确保不丢失。"""
    if os.path.exists(_VOCAB_FILE):
        try:
            with open(_VOCAB_FILE, "r", encoding="utf-8") as f:
                vocab = json.loads(f.read())
            for mood, data in _BUILTIN.items():
                if mood not in vocab:
                    vocab[mood] = {}
                for key in ["zh", "en", "策略", "优先级"]:
                    if key not in vocab[mood]:
                        vocab[mood][key] = data.get(key, [])
                    elif isinstance(data[key], list):
                        existing = set(vocab[mood][key])
                        existing.update(data[key])
                        vocab[mood][key] = sorted(existing)
            return vocab
        except Exception:
            pass

    vocab = {mood: {k: v for k, v in data.items()} for mood, data in _BUILTIN.items()}
    save_vocab(vocab)
    return vocab


def save_vocab(vocab: dict):
    os.makedirs(os.path.dirname(_VOCAB_FILE), exist_ok=True)
    with open(_VOCAB_FILE, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)


def learn(word: str, mood: str, lang: str = "zh") -> bool:
    """学习新情绪词。"""
    vocab = load_vocab()
    if mood not in vocab:
        return False
    if lang not in vocab[mood]:
        vocab[mood][lang] = []
    if word not in vocab[mood][lang]:
        vocab[mood][lang].append(word)
        vocab[mood][lang] = sorted(vocab[mood][lang])
        save_vocab(vocab)
        return True
    return False


def detect(message: str) -> dict:
    """检测情绪：返回 {mood, emitter, keywords, strategy, priority}。"""
    vocab = load_vocab()
    msg_lower = message.lower()

    # 按优先级排序检测：放弃 > 愤怒 > 悲伤 > 焦虑 > 其他
    mood_order = ["放弃", "愤怒", "悲伤", "焦虑", "困惑", "意外", "开心"]

    for mood in mood_order:
        all_words = vocab.get(mood, {}).get("zh", []) + vocab.get(mood, {}).get("en", [])
        for word in sorted(all_words, key=len, reverse=True):
            if word.lower() in msg_lower:
                idx = msg_lower.find(word.lower())
                ctx = message[max(0, idx-30):idx].lower()

                if any(w in ctx for w in _SUBJECT_OTHERS):
                    emitter = "他人"
                elif any(w in ctx for w in _SUBJECT_IMPACT):
                    emitter = "影响"
                else:
                    emitter = "自我"

                return {
                    "mood": mood,
                    "emitter": emitter,
                    "keywords": [word],
                    "strategy": vocab[mood].get("策略", ""),
                    "priority": vocab[mood].get("优先级", "低"),
                }

    return {"mood": "", "emitter": "自我", "keywords": [], "strategy": "", "priority": "低"}


def mood_message(detection: dict) -> str:
    """管家回应。"""
    mood = detection["mood"]
    emitter = detection["emitter"]
    words = detection["keywords"][:2]
    strat = detection.get("strategy", "")

    if not mood:
        return ""

    emoji_map = {
        "愤怒": "😡", "悲伤": "😢", "焦虑": "😰", "放弃": "🔴",
        "开心": "😊", "困惑": "🤔", "意外": "😲",
    }
    emoji = emoji_map.get(mood, "🟡")

    if emitter == "他人":
        return f"{emoji} 觉察：别人{mood}——「{'、'.join(words)}」。不影响你的状态。"
    elif emitter == "影响":
        return f"{emoji} 觉察：别人的情绪影响到你了——「{'、'.join(words)}」。{strat}"
    elif mood == "放弃":
        return f"🔴 红牌——「{'、'.join(words)}」。优先级=自我修正。{strat}"
    else:
        return f"{emoji} 觉察：{mood}——「{'、'.join(words)}」。{strat}"
