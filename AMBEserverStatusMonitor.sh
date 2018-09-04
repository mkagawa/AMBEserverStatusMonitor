#!/usr/bin/env bash
cd /boot
echo $BASHPID > /run/ambedstatus.pid
export LANG=C
exec /boot/led11.py >/boot/monitor.txt
