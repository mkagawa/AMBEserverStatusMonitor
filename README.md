# AMBEserverStatusMonitor

## Motivation
this project is for AMBE portable server, a headless device, to display current network status by using RP-Zero built-in LED.

## Description
this program is running as systemd service. take control of LED, and blinks to by pattern.

## Meaning of LED flash patterns
LED flashes every 6 seconds if status is normal. Otherwise flashes short cycle with combination of long and short flashes, 
which is based on morse code letter.

|LED flashes|Morse|Meaning                                                 |
|-----------|-----|--------------------------------------------------------|
|L,S,S,L    | X   |Could not use configured IP address (wrong or duplicate)|
|S,L,L      | W   |Wifi configuration problem                              |
|S,L,L,S    | P   |G/W IP doesn't respond to PING                          |
|L,L,S      | G   |G/W not in route. configuration error                   |

## License

The MIT License (MIT)

Copyright (c) 2018 Masa Kagawa (NW6UP) mkagawa@hotmail.com

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

