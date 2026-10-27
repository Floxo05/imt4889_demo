FROM python:3.14-alpine

WORKDIR /app

COPY requirements.txt /app
RUN pip install -r requirements.txt

COPY --chown=1001:1001 . .

RUN mkdir -p /app/uploads && chown -R 1001:1001 /app

RUN addgroup -g 1001 appgroup && adduser -D -u 1001 -G appgroup appuser
ENV USER=appuser
USER 1001

EXPOSE 5000

ENTRYPOINT ["python3"]
CMD ["app.py"]