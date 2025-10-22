FROM otel/opentelemetry-collector-contrib:0.138.0 AS collector

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    logrotate tini ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App + logrotate config + starter
COPY app/log_generator.py .
COPY logrotate/app.conf /etc/logrotate.d/app.conf
COPY logrotate/logrotate-loop.sh /usr/local/bin/logrotate-loop.sh
COPY otelcol/config.yaml /etc/otelcol/config.yaml
COPY start.sh /usr/local/bin/start.sh
RUN mkdir -p /var/lib/opentelemetry-collector /var/log/opentelemetry-collector &&\
    chmod +x /usr/local/bin/start.sh /usr/local/bin/logrotate-loop.sh

COPY --from=collector /otelcol-contrib /otelcol-contrib

ENTRYPOINT ["tini", "--"]
CMD ["/usr/local/bin/start.sh"]
