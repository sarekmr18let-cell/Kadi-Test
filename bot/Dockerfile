FROM python:3.12-slim

WORKDIR /app

# aiogram >=3.13 is needed for Telegram Business updates (business_message).
RUN pip install --no-cache-dir "aiogram>=3.13,<4.0" httpx==0.27.0

COPY . .

CMD ["python", "main.py"]
