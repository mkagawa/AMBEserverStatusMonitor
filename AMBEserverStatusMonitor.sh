#!/usr/bin/env bash
cd /boot
echo $BASHPID > /run/ambedstatus.pid
export LANG=C
exec stdbuf -e0 -o0 /boot/led11.py >/boot/monitor.txt
