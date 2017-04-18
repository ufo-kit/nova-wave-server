import sys
import json
import time
import argparse
import requests


def check_range(l):
    for x in l:
        if x < 0.0 or x > 1.0:
            sys.exit("Error: numbers must be within [0.0, 1.0].")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', type=float, nargs='+', default=[0.0, 0.0, 0.0])
    parser.add_argument('--dimensions', type=float, nargs='+', default=[1.0, 1.0])
    parser.add_argument('--subset', type=int, default=0)
    parser.add_argument('--size', type=int, default=256)
    parser.add_argument('--path', type=str, required=True)
    args = parser.parse_args()

    if len(args.origin) != 3:
        sys.exit("Error: `origin' must be a list with three elements.")

    if len(args.dimensions) != 2:
        sys.exit("Error: `dimensions' must be a list with two elements.")

    check_range(args.origin)
    check_range(args.dimensions)

    # POST request
    data = dict(origin=args.origin, dimensions=args.dimensions, size=args.size,
                subset=args.subset, path=args.path)

    r = requests.post('http://localhost:5000/maps', json=data)
    r.raise_for_status()
    url = r.headers['Location']

    # Check process queue
    while True:
        r = requests.get(url)
        r.raise_for_status()

        if r.json()['status'] == 'done':
            # Download image
            url = r.headers['Location']
            r = requests.get(url, stream=True)
            r.raise_for_status()

            with open('output.jpg', 'wb') as f:
                for chunk in r:
                    f.write(chunk)

            break

        time.sleep(1.0)
