# xmr_haystack

## Description

This program takes a Monero wallet file, scans the blockchain, and outputs transactions in which
your one-time public outputs (stealth addresses) were used as decoys.

## Usage

```
usage: python main.py [-h] [-a ADDR] [-p PORT] [-l LOGIN] [-s HEIGHT] [-i CACHE_IN] [-o CACHE_OUT] [-n] [-c CLI_EXE_FILE]
                    wallet file

America's favorite stealth address scanner™

positional arguments:
  wallet file           path to wallet file

optional arguments:
  -h, --help            show this help message and exit
  -a ADDR, --daemon-addr ADDR
                        daemon address (e.g. node.xmr.to)
  -p PORT, --daemon-port PORT
                        daemon port (e.g. 18081)
  -l LOGIN, --daemon-login LOGIN
                        monerod RPC login in the form of [username]:[password]
  -s HEIGHT, --scan-height HEIGHT
                        rescan blockchain from specified height. defaults to wallet restore height
  -i CACHE_IN, --cache-input CACHE_IN
                        path to input cache file
  -o CACHE_OUT, --cache-output CACHE_OUT
                        path to output cache file
  -n, --no-cache        do not read from cache file and do not save to cache file
  -c CLI_EXE_FILE, --wallet-cli-path CLI_EXE_FILE
                        path to monero-wallet-cli executable. Helpful if executable is not in PATH
```

## Disclaimer

While this program works, it is still in *very* early dev stages. Use this program at your own risk;
I take no responsibility for any lost funds or privacy, etc, etc. That said, I really hope you find
this code useful and I would really appreciate any feedback. :)
