# Vídeos de manutenção industrial

Vídeos curtos (TikTok) sobre manutenção no chão de fábrica, gerados automaticamente.

- `pipeline/make_video.py roteiro.json saida.mp4` — monta o vídeo (cortes de ~2,5 s com cenas Pixabay, narração neural pt-BR, legenda palavra a palavra, música de fundo). Requer `PIXABAY_KEY`, `ffmpeg`, `pip install edge-tts gtts pillow requests numpy`.
- `roteiros/` — roteiro de cada vídeo publicado (evita repetir temas).
- `videos/` — vídeos finais, servidos via raw.githubusercontent.com para o Metricool.
