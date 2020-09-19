# xmr_haystack

## Description

This program takes a Monero wallet file, scans the blockchain, and outputs transactions in which your one-time public outputs
(stealth addresses) were used as decoys.  

## Usage

```

usage: xmr-haystack [-h] [-a ADDR] [-p PORT] [-l LOGIN] [-s HEIGHT] [-c CLI_EXE_FILE] wallet file

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
  -c CLI_EXE_FILE, --wallet-cli-path CLI_EXE_FILE
                        path to monero-wallet-cli executable. Helpful if executable is not in PATH

```

## Disclaimer

While this program works, it is still in *very* early dev stages, and some of the command-line arguments are non-functional.
The ones listed in the README should be valid. Use this program at your own risk; I take no responsibility for any lost funds
or privacy, etc, etc. That said, I really hope you find this code useful and I would really appreciate any feedback. :)
