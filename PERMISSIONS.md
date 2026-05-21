# Nexus Intelligence — Windows permissions (full control)

## Zaroori (har user)

| Permission | Kaise enable |
|------------|----------------|
| **Microphone** | Settings → Privacy → Microphone → On, Python/Chrome allow |
| **Internet** | OpenRouter/Groq API, Chrome STT, web search |
| **MongoDB** | Local `mongodb://localhost:27017` (Compass optional) |

## Strong control (apps, windows, volume)

| Kaam | Permission |
|------|------------|
| Chrome / YouTube / apps khulna | Normal user — `cmd start` + mapped apps |
| Window minimize/maximize | Normal user — Windows API |
| Volume mute/up/down | `keyboard` library — kabhi-kabhi **Admin** chahiye |
| Screen padhna (vision) | OpenRouter + Gemini model + screenshot |

## Shutdown / restart (dangerous)

1. `.env` mein likho:
   ```
   AllowShutdown=true
   ShutdownDelaySec=60
   ```
2. **PowerShell / CMD → Run as Administrator**
3. Phir:
   ```powershell
   cd C:\Users\Administrator\Downloads\jarvis-ai\jarvis-ai
   .\.venv\Scripts\Activate.ps1
   py Main.py
   ```
4. Cancel shutdown: bolo **"shutdown cancel"** ya CMD: `shutdown /a`

## Administrator kab chahiye?

- System **shutdown / restart**
- Kuch apps install path se open (Program Files)
- Antivirus agar Python block kare
- Volume keys agar kaam na karein

## Optional (better STT)

- Google Chrome installed (voice recognition page)
- Mic default device sahi set

## Security note

Nexus aapke PC pe **sach mein** commands chalati hai. `AllowShutdown=true` sirf tab rakho jab trust ho. Git mein `.env` commit mat karo.
