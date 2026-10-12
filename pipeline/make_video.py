"""Monta um vídeo vertical (1080x1920) para TikTok a partir de um roteiro JSON.

Uso: PIXABAY_KEY=... python3 make_video.py roteiro.json saida.mp4

Roteiro:
{"marca": "...", "serie": "Erros de manutenção #3" (opcional),
 "cenas": [{"tela": "título curto da cena", "fala": "narração",
            "ids": [ids de vídeos Pixabay, 1 a 3 por cena]}]}

Formato: cortes a cada ~2,5 s, legenda palavra a palavra sincronizada com a voz,
título da cena no topo, música de fundo baixa. Voz pt-BR-AntonioNeural (edge-tts);
com VOICE_FALLBACK=1 usa gTTS se a voz neural falhar.
Deixa s0.mp4, s1.mp4... no diretório atual para a verificação visual.
"""
import asyncio, json, os, subprocess, sys, textwrap, wave
import numpy as np, requests
from PIL import Image, ImageDraw, ImageFont

CA = "/root/.ccr/ca-bundle.crt"  # proxy do ambiente de nuvem
if os.path.exists(CA):
    import certifi
    certifi.where = lambda: CA
    os.environ.setdefault("REQUESTS_CA_BUNDLE", CA)

KEY = os.environ["PIXABAY_KEY"]
W, H, FPS, CUT = 1080, 1920, 30, 2.5
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VOICE = "pt-BR-AntonioNeural"


def run(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)


def duration(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]))


def tts(text, out):
    """Gera a narração e devolve [(início_s, fim_s, palavra)]."""
    try:
        import edge_tts

        async def go():
            words = []
            c = edge_tts.Communicate(text, VOICE, rate="+12%", boundary="WordBoundary")
            with open(out, "wb") as f:
                async for m in c.stream():
                    if m["type"] == "audio":
                        f.write(m["data"])
                    elif m["type"] == "WordBoundary":
                        s = m["offset"] / 1e7
                        words.append((s, s + m["duration"] / 1e7, m["text"]))
            return words

        return asyncio.run(go())
    except Exception:
        if os.environ.get("VOICE_FALLBACK") != "1":
            raise
        from gtts import gTTS
        gTTS(text, lang="pt", tld="com.br").save("g.mp3")
        run("-i", "g.mp3", "-filter:a", "atempo=1.25", out)
        ws, d = text.split(), duration(out)
        tot = sum(len(w) + 1 for w in ws)
        t, words = 0.1, []
        for w in ws:
            dt = (d - 0.2) * (len(w) + 1) / tot
            words.append((t, t + dt, w))
            t += dt
        return words


def clip(vid):
    path = f"clip_{vid}.mp4"
    if not os.path.exists(path):
        h = requests.get("https://pixabay.com/api/videos/", params=dict(key=KEY, id=vid), timeout=30).json()["hits"][0]
        url = h["videos"]["medium"]["url"] or h["videos"]["small"]["url"]
        open(path, "wb").write(requests.get(url, timeout=120).content)
    return path


def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def captions(words, path):
    """Legenda em blocos de até 3 palavras; a palavra falada fica amarela."""
    head = ("[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginV\n"
            "Style: C,DejaVu Sans,96,&H00FFFFFF,&H00000000,&H64000000,1,1,7,3,5,0\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Text\n")
    events, groups = [], [words[i:i + 3] for i in range(0, len(words), 3)]
    for g in groups:
        for k, (s, e, _) in enumerate(g):
            txt = " ".join(("{\\c&H00D7FF&}" + w.upper() + "{\\c&HFFFFFF&}") if j == k else w.upper()
                           for j, (_, _, w) in enumerate(g))
            events.append([s, e + 0.15, txt])
    # Um bloco some exatamente quando o próximo aparece: nunca há duas legendas na tela.
    for a, b in zip(events, events[1:]):
        a[1] = b[0]
    lines = [f"Dialogue: 0,{ass_time(s)},{ass_time(e)},C,{{\\pos(540,1180)}}{t}" for s, e, t in events]
    open(path, "w").write(head + "\n".join(lines) + "\n")


def overlay(marca, tela, serie, path):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 130], fill=(0, 0, 0, 170))
    d.text((40, 45), serie or marca, font=ImageFont.truetype(BOLD, 40), fill=(255, 170, 0))
    if tela:
        f = ImageFont.truetype(BOLD, 64)
        lines = textwrap.wrap(tela.upper(), 22)
        y = 230
        d.rectangle([0, y - 30, W, y + len(lines) * 82 + 20], fill=(0, 0, 0, 150))
        for l in lines:
            w = d.textlength(l, font=f)
            d.text(((W - w) / 2, y), l, font=f, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
            y += 82
    im.save(path)


def music(dur, path, sr=44100):
    """Trilha ambiente sintetizada (sem direitos autorais): acordes suaves + pulso a 100 bpm."""
    t = np.arange(int(dur * sr)) / sr
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]
    sig = np.zeros_like(t)
    bar = 2.4
    for i, ch in enumerate(chords * int(dur / bar / 4 + 2)):
        a, b = int(i * bar * sr), int((i + 1) * bar * sr)
        if a >= len(t):
            break
        tt = t[a:b] - t[a]
        env = np.minimum(1, tt / 0.4) * np.minimum(1, (bar - tt) / 0.4)
        sig[a:b] += sum(np.sin(2 * np.pi * f * tt) for f in ch) * env / 3
    beat = 0.6
    for k in range(int(dur / beat)):
        a = int(k * beat * sr)
        n = min(int(0.15 * sr), len(t) - a)
        tt = np.arange(n) / sr
        sig[a:a + n] += 0.8 * np.sin(2 * np.pi * (60 - 30 * tt) * tt) * np.exp(-tt * 25)
    sig = (sig / np.abs(sig).max() * 0.5 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(sig.tobytes())


def main():
    spec = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    segs = []
    for i, c in enumerate(spec["cenas"]):
        words = tts(c["fala"], f"v{i}.mp3")
        dur = duration(f"v{i}.mp3") + 0.15
        captions(words, f"c{i}.ass")
        overlay(spec["marca"], c.get("tela"), spec.get("serie"), f"o{i}.png")
        ids = c["ids"]
        n = max(1, round(dur / CUT))
        parts = []
        for k in range(n):
            p = f"p{i}_{k}.mp4"
            src = clip(ids[k % len(ids)])
            off = (k // len(ids)) * CUT % max(0.1, duration(src) - CUT)
            run("-ss", str(off), "-stream_loop", "-1", "-i", src, "-t", str(dur / n),
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", p)
            parts.append(p)
        open("parts.txt", "w").write("".join(f"file '{p}'\n" for p in parts))
        run("-f", "concat", "-safe", "0", "-i", "parts.txt", "-i", f"o{i}.png", "-i", f"v{i}.mp3",
            "-filter_complex", f"[0:v][1:v]overlay=0:0,ass=c{i}.ass[o]", "-map", "[o]", "-map", "2:a",
            "-t", str(dur), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", f"s{i}.mp4")
        segs.append(f"s{i}.mp4")
    open("list.txt", "w").write("".join(f"file '{s}'\n" for s in segs))
    run("-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "voz.mp4")
    total = duration("voz.mp4")
    music(total, "musica.wav")
    run("-i", "voz.mp4", "-i", "musica.wav", "-filter_complex",
        "[1:a]volume=0.10,afade=t=out:st=%.2f:d=1[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]" % max(0, total - 1),
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-ac", "2", out)


if __name__ == "__main__":
    main()
