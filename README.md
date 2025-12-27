# twic-dl
script for downloading from TWIC: The week in chess

# Prerequisites
pip install requests

# Usage

1) Download e.g. 1600-1623, extract and merge into one file:
    python3 twic-dl.py --start 1600 --end 1623 --extract --merge twic_1600_1623.pgn

2) Get up to 1500, as issues will be depleted (stop after 3 x 404)
    python3 twic-dl.py --start 1500 --extract --merge twic_from_1500.pgn

3) use --no-head
    python3 twic-dl.py --start 1600 --end 1623 --no-head
