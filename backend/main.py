"""
Entry point dell'applicazione.
Avvia FastAPI (web app + API) con uvicorn.
Il bot Telegram e lo scheduler partono nel lifespan di FastAPI (backend/app.py).
"""
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main():
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
