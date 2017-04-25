import os
import hashlib
import subprocess
import tifffile
import shlex
import requests
import json
from multiprocessing import Process
from flask import Flask, request, jsonify, abort, url_for, send_file

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['NOVA_API_URL'] = 'http://localhost:5000/api'
jobs = {}


def split_identifier(map_id):
    return map_id[:2], map_id[2:4], map_id[4:]


def identifier_to_path(map_id):
    return os.path.join('cache', *split_identifier(map_id)) + '.jpg'


def abort_for_status(response):
    if response.status_code != 200:
        try:
            message = json.loads(response.text)
            abort(response.status_code, message['message'])
        except ValueError:
            abort(response.status_code)


def create(map_id, data_path, subset, origin, dimensions, size):
    output_path = identifier_to_path(map_id)

    if os.path.exists(output_path):
        return 0

    if not os.path.exists(data_path):
        app.logger.error('{} does not exist'.format(data_path))
        return -1
    
    first, second, name_prefix = split_identifier(map_id)

    path = os.path.join('cache', first)

    if not os.path.exists(path):
        os.mkdir(path)

    path = os.path.join(path, second)

    if not os.path.exists(path):
        os.mkdir(path)

    x, y, z = origin
    w, h = dimensions
    files = [os.path.join(data_path, f) for f in sorted(os.listdir(data_path)) if f.endswith('tif')]
    data = tifffile.imread(files[0])
    height, width = data.shape
    number = 8 * 8
    xa = int(x * width)
    ya = int(y * height)

    parameters = dict(path=data_path, output=output_path,
                      x=xa, y=ya, za=int(z * len(files)),
                      w=int(min(width - xa, w * width)), h=int(min(height - ya, h * height)),
                      size=size, number=number, start=subset * number)

    cmd = "ufo-launch read path={path} number={number} start={start} ! " \
        "crop x={x} y={y} width={w} height={h} ! " \
        "rescale width={size} height={size} ! " \
        "map-slice number={number} ! write filename={output}".format(**parameters)

    output = subprocess.call(shlex.split(cmd))


@app.route('/maps', methods=['POST'])
def make_map():
    # authenticate for path access
    headers = {'Auth-Token': request.json['token']}
    url = '{}/datasets/{}'.format(app.config['NOVA_API_URL'], request.json['dataset'])
    r = requests.get(url, headers=headers)
    abort_for_status(r)

    # generate a unique map_id from the parameters
    path = os.path.join(r.json()['path'], 'slices')
    subset = request.json.get('subset', 0)
    origin = request.json.get('origin', [0.0, 0.0, 0.0])
    dimensions = request.json.get('dimensions', [1.0, 1.0])
    size = request.json.get('size', 256)
    identifier = "p={},s={},o={},d={}".format(path, subset, origin, dimensions)
    map_id = hashlib.sha256(identifier).hexdigest()

    args = (map_id, path, subset, origin, dimensions, size)
    process = Process(target=create, args=args)
    process.start()
    jobs[map_id] = process

    response = jsonify()
    response.headers['location'] = url_for('check_queue', map_id=map_id)
    return response


@app.route('/maps/<map_id>', methods=['GET'])
def get_map(map_id):
    path = identifier_to_path(map_id)

    if not os.path.exists(path):
        abort(404)

    return send_file(path, mimetype='image/jpeg')


@app.route('/queue/<map_id>', methods=['GET'])
def check_queue(map_id):
    response = jsonify(status='done')
    response.headers['location'] = url_for('get_map', map_id=map_id)

    if map_id not in jobs:
        return response

    # race condition!
    job = jobs[map_id]

    if job.is_alive():
        return jsonify(status='running')

    del jobs[map_id]
    return response


if __name__ == '__main__':
    app.run()
