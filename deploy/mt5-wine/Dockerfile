FROM ubuntu:24.04

ENV WINEARCH=win64     WINEPREFIX=/root/.wine     DEBIAN_FRONTEND=noninteractive     DISPLAY=:99

RUN dpkg --add-architecture i386     && apt-get update     && apt-get install -y --no-install-recommends         wine64 wine32:i386 winetricks xvfb wget cabextract unzip ca-certificates     && rm -rf /var/lib/apt/lists/*

RUN wget -q https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe -O /tmp/python-installer.exe     && xvfb-run wine /tmp/python-installer.exe /quiet InstallAllUsers=1 PrependPath=1     && rm /tmp/python-installer.exe

RUN xvfb-run wine "C:\Program Files\Python311\python.exe" -m pip install --no-cache-dir MetaTrader5 rpyc

RUN xvfb-run -a bash -c "winetricks -q vcrun2019; wineserver -w"

RUN wget -q https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe -O /tmp/mt5setup.exe     && xvfb-run -a bash -c "wine /tmp/mt5setup.exe /auto; wineserver -w"     && rm /tmp/mt5setup.exe

COPY rpyc_server.py /opt/rpyc_server.py
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

EXPOSE 18812
ENTRYPOINT ["/opt/entrypoint.sh"]
