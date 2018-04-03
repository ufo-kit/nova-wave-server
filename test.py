import sys
import json
import time
import argparse
import requests



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=str, default='http://localhost:5001')
    parser.add_argument('--origin', type=float, nargs='+', default=[0.0, 0.0, 0.0])
    parser.add_argument('--dimensions', type=float, nargs='+', default=[1.0, 1.0])
    parser.add_argument('--subset', type=int, default=0)
    parser.add_argument('--size', type=int, default=256)
    parser.add_argument('--token', type=str, required=True)
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--user', type=str, required=True)
    args = parser.parse_args()

    if len(args.origin) != 3:
        sys.exit("Error: `origin' must be a list with three elements.")

    if len(args.dimensions) != 2:
        sys.exit("Error: `dimensions' must be a list with two elements.")

    # POST request
    data = dict(token=args.token, user=args.user, dataset=args.dataset, origin=args.origin,
                dimensions=args.dimensions, size=args.size, subset=args.subset)

    r = requests.post('{}/maps'.format(args.server), json=data)
    r.raise_for_status()
    url = r.headers['Location']

    # Check process queue
    while True:
        r = requests.get(url)
        r.raise_for_status()

        if r.json()['status'] == 'done':
            # Download image
            url = '{}/{}'.format(r.headers['Location'], args.subset)
            r = requests.get(url, stream=True)
            r.raise_for_status()

            with open('output.jpg', 'wb') as f:
                for chunk in r:
                    f.write(chunk)

            break

        time.sleep(1.0)
