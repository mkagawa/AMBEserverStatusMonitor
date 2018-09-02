#!/usr/bin/env bash
echo $BASHPID > /run/ambedstatus.pid
export LANG=C
exec /boot/led11.py
