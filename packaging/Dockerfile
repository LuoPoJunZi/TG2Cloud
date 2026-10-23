FROM python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/opt/tg2cloud:/opt/tg2cloud/app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates rclone tini tzdata \
    && groupadd --system --gid 10001 tg2cloud \
    && useradd --system --uid 10001 --gid 10001 --home-dir /nonexistent \
        --shell /usr/sbin/nologin tg2cloud \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/tg2cloud
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# Public source must be readable by UID 10001 even from a private CLI staging
# directory. Keep root ownership: the runtime user must not modify this code.
RUN chmod -R a+rX app

USER 10001:10001

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "tg2cloud.app"]
