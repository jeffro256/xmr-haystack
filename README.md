# xmr-haystack

## Description

This program takes a Monero wallet file, scans the blockchain, and outputs transactions in which
your one-time public outputs (stealth addresses) were used as decoys.

## Installation

A Python 3 environment is required to run this application. Given that you have a working Python 3
environment, all you need to do to install this application is run the following command:

```
$ pip3 install xmr-haystack
```

If you are on Linux or MacOS and you would prefer to build from the source code, then the following
commands will allow you to do so:

```
$ git clone https://github.com/jeffro256/xmr-haystack.git
$ cd xmr-haystack
$ pip3 install .
```

If you are Windows and would prefer to build from the source code, then follow these steps:

1. Download the unzip source code from [Github](https://github.com/jeffro256/xmr-haystack).
2. Open 'cmd' from the Start Menu
3. Naviagte to newly unzipped directory in cmd
4. Type `$ pip3 install .`

## Usage

```
python3 -m xmr-haystack [-h] [-a ADDR] [-p PORT] [-l LOGIN] [-s HEIGHT] [-q | -Q] [-i CACHE_IN] [-o CACHE_OUT] [-n] 
                        [-c CLI_EXE_FILE] wallet file

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
  -q, --quiet           use this flag if you would like a simpler output
  -Q, --extra-quiet     use this flag if you would like a BARE BONES output
  -i CACHE_IN, --cache-input CACHE_IN
                        path to input cache file
  -o CACHE_OUT, --cache-output CACHE_OUT
                        path to output cache file
  -n, --no-cache        do not read from cache file and do not save to cache file
  -c CLI_EXE_FILE, --wallet-cli-path CLI_EXE_FILE
                        path to monero-wallet-cli executable. Helpful if executable is not in PATH
```

### Example

```
$ python -m xmr-haystack Documents/mywallet/mywallet

...
Your stealth address: 58ddd530a2148ca67f914823bab3e5b30f10be16b5a17ca194a022e279fb9258
    [2019-10-28 14:49:50]: Pubkey was created. Transaction(hash=f889ab737e12a88f249762e15fdcf2e0fa5a3f2d124d63860c029e57a61d33b6, height=1954776, ins=22, outs=2)
    [2019-10-28 17:20:56]: Used as a decoy. Transaction(hash=41662618c3fe6556a1b69128be7ff731565fb5d3003d03296587bc3d9985e01b, height=1954856, ins=11, outs=2)
    [2019-10-28 20:46:02]: Used as a decoy. Transaction(hash=ce3d73fd5f47ed3205d5f4d3a5246a7d3adf09ab6fb9238ac8f5d0c3976874d3, height=1954958, ins=11, outs=2)
    [2019-10-29 01:06:24]: Used as a decoy. Transaction(hash=76be4fa1b0089e2dec7332adf0230294e9c94ec4e32be44d65830ba2f0ecb1c3, height=1955092, ins=814, outs=2)
    [2019-10-29 07:03:25]: Used as a decoy. Transaction(hash=28277d27a738543257414e3f5f4b71eed5d3551fa815c22a66c7183cf38ebcd1, height=1955280, ins=22, outs=2)
    [2019-10-29 12:39:36]: Used as a decoy. Transaction(hash=1e3e89a8be3af614ce06324d1c61c16ed4cf84fcbf39095be84cbe3875fd0644, height=1955443, ins=11, outs=2)
    [2019-10-29 16:27:17]: Used as a decoy. Transaction(hash=1e2e63f61222809178476a7dcb7b2b5aaba060b23cfc95c9c797bfb3d233b92f, height=1955566, ins=187, outs=2)
    [2020-07-15 00:26:23]: Pubkey was spent. Transaction(hash=a6cbb9f76f9b37247c9f3fb160dccdf5d627b92702a09c488815cf8bcd9baf70, height=2142546, ins=11, outs=2)
...

```

## Disclaimer

While this program works, it is still in *very* early dev stages. Use this program at your own risk;
I take no responsibility for any lost funds or privacy, etc, etc. That said, I really hope you find
this code useful and I would really appreciate any feedback. :)

## Donate

89tQx7bUmQDMdkgUjk5ZSfVpV3yGKZ6udWe4XGbBNE27iyxoYoWif8nHCLnvqjodaLENVGgBpWSFE2XGyjNKLT1bB8efQh5

