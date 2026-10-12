# Vídeos de manutenção industrial

Vídeos curtos (TikTok) sobre manutenção no chão de fábrica, gerados automaticamente.

- `pipeline/make_video.py roteiro.json saida.mp4` — monta o vídeo (cenas Pixabay + narração neural pt-BR + legendas). Requer `PIXABAY_KEY`, `ffmpeg`, `pip install edge-tts pillow requests`.
- `roteiros/` — roteiro de cada vídeo publicado (evita repetir temas).
- `videos/` — vídeos finais, servidos via raw.githubusercontent.com para o Metricool.
