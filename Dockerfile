# Base image: Ubuntu 22.04 LTS
FROM ubuntu:22.04

LABEL maintainer="Railway Android Cloud"
ENV DEBIAN_FRONTEND=noninteractive \
    ANDROID_HOME=/opt/android-sdk \
    DATA_DIR=/data \
    UPLOADS_DIR=/uploads \
    PORT=8000 \
    DISPLAY=:0

ENV PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/emulator:${PATH}"

# 1. Install system packages & dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    openjdk-17-jdk-headless \
    curl \
    wget \
    unzip \
    git \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    adb \
    aapt \
    libpulse0 \
    libglu1-mesa \
    libgl1-mesa-glx \
    libgl1-mesa-dri \
    mesa-utils \
    procps \
    net-tools \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Copy scripts and install Android SDK components (pre-baked in Docker image)
COPY scripts/install-android.sh /app/scripts/install-android.sh
RUN chmod +x /app/scripts/install-android.sh && /bin/bash /app/scripts/install-android.sh

# 4. Install Python dependencies
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Copy project source files
COPY server/ /app/server/
COPY web/ /app/web/
COPY scripts/ /app/scripts/
COPY start.sh /app/start.sh
COPY railway.toml /app/railway.toml

# 6. Ensure scripts are executable & link noVNC web assets
RUN chmod +x /app/scripts/*.sh /app/start.sh && \
    mkdir -p /data /uploads && \
    ln -s /usr/share/novnc /app/web/novnc

# 7. Expose volumes and default port
VOLUME ["/data", "/uploads"]
EXPOSE 8000

# 8. Entrypoint
CMD ["/bin/bash", "/app/start.sh"]
