"""
Hermes TTS Bridge - 刘浩存声音
使用 edge-tts 语音合成 + 基础声音适配
"""
import os
import asyncio
import io
import uuid
import json
from fastapi import FastAPI, Query
from fastapi.responses import Response, FileResponse
import uvicorn
import edge_tts
import numpy as np
import soundfile as sf

app = FastAPI(title="Hermes TTS Bridge")

# 刘浩存声音特征参数
LIU_HAOCUN = {
    "pitch_shift": 2.9,  # 半音
}
REF_WAV = os.path.expanduser("~/.neurobase/liuhaocun_audio/liuhaocun_ruxi_16k.wav")

# 先测试librosa是否可用
try:
    import librosa
    HAS_LIBROSA = True
except:
    HAS_LIBROSA = False

async def generate_edge_tts(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    """生成 edge-tts 语音"""
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

def apply_voice_adaptation(mp3_bytes: bytes) -> bytes:
    """
    用 librosa 做声音适配（如果有的话）
    否则原样返回 edge-tts 输出
    """
    if not HAS_LIBROSA:
        # 没librosa就返回MP3，让浏览器/客户端自己解码
        return mp3_bytes
    
    try:
        import librosa
        import tempfile
        
        # 写临时文件
        tmp_in = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")
        tmp_out = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.wav")
        
        try:
            with open(tmp_in, "wb") as f:
                f.write(mp3_bytes)
            
            # 读入音频
            y, sr = librosa.load(tmp_in, sr=24000, mono=True)
            
            # 音高偏移（匹配刘浩存音高）
            y = librosa.effects.pitch_shift(
                y=y, sr=sr, 
                n_steps=LIU_HAOCUN["pitch_shift"],
                bins_per_octave=24
            )
            
            # 归一化
            peak = np.max(np.abs(y))
            if peak > 0:
                y = y / peak * 0.95
            
            # 写WAV
            sf.write(tmp_out, y, sr, subtype="PCM_16")
            with open(tmp_out, "rb") as f:
                result = f.read()
            return result
        finally:
            # 清理
            for p in [tmp_in, tmp_out]:
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except:
                    pass
    except Exception as e:
        print(f"[WARN] 声音适配失败: {e}，返回原始edge-tts")
        return mp3_bytes

@app.get("/tts")
async def tts(text: str = Query(..., min_length=1, max_length=500)):
    """文本转语音（刘浩存风格）"""
    print(f"[TTS] '{text}'")
    
    # 生成
    mp3_data = await generate_edge_tts(text)
    
    # 声音适配
    audio = apply_voice_adaptation(mp3_data)
    
    # 判断返回类型
    if audio[:4] == b'RIFF':  # WAV
        return Response(content=audio, media_type="audio/wav")
    else:  # MP3
        return Response(content=audio, media_type="audio/mpeg")

@app.get("/health")
async def health():
    return {"status": "ok", "voice": "刘浩存", "librosa": HAS_LIBROSA}

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════╗
    ║  Hermes TTS Bridge - 刘浩存声音  ║
    ║  http://localhost:8765           ║
    ╚══════════════════════════════════╝
    """)
    uvicorn.run(app, host="127.0.0.1", port=8765)
