FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip --no-cache-dir install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]