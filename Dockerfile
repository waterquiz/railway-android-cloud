# syntax=docker/dockerfile:1
# check=skip=all
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV DATA_DIR=/data
ENV UPLOADS_DIR=/uploads
ENV PORT=8000
ENV DISPLAY=:0
ENV PATH=/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

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
    fluxbox \
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

# 3. Copy scripts and install Android SDK components
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

# 6. Ensure scripts are executable & link noVNC web assets
RUN chmod +x /app/scripts/*.sh /app/start.sh && \
    mkdir -p /data /uploads && \
    ln -s /usr/share/novnc /app/web/novnc

# 7. Expose default port
EXPOSE 8000

# 8. Entrypoint
CMD ["/bin/bash", "/app/start.sh"]
