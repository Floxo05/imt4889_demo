FROM python:3.14-alpine

RUN apk add --no-cache sqlite
RUN addgroup -g 1001 appgroup && adduser -D -u 1001 -G appgroup appuser

WORKDIR /app

COPY requirements.txt /app
RUN pip install -r requirements.txt gunicorn

COPY --chown=1001:1001 . .

RUN mkdir -p /app/uploads && chown -R 1001:1001 /app

ENV USER=appuser
USER 1001

EXPOSE 5000

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]