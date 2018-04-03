import os
import hashlib
import subprocess
import tifffile
import shlex
import requests
import json
import atexit
import socket
from multiprocessing import Process
from flask import Flask, request, jsonify, abort, url_for, send_file
from flask_script import Manager
from flask_cors import CORS

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['NOVA_API_URL'] = 'http://localhost:5000/api'
CORS(app, expose_headers=['location'])

SERVICE_NAME = 'wave-slicemap-server'
SERVICE_DESCRIPTION = """WAVE slice map server"""
SERVICE_SECRET = '123'

manager = Manager(app)

jobs = {}
subsets = {}

def check_range(l):
    for x in l:
        if x < 0.0 or x > 1.0:
            abort(400, "Error: numbers must be within [0.0, 1.0].")


def split_identifier(map_id):
    return map_id[:2], map_id[2:4], map_id[4:]


def identifier_to_path(map_id):
    return os.path.join('cache', *split_identifier(map_id))


def abort_for_status(response):
    if response.status_code != 200:
        try:
            message = json.loads(response.text)
            abort(response.status_code, message['message'])
        except ValueError:
            abort(response.status_code)


def create(map_id, data_path, subsets, origin, dimensions, size):
    output_path = identifier_to_path(map_id)

    if os.path.exists(output_path):
        return 0

    if not os.path.exists(data_path):
        app.logger.error('{} does not exist'.format(data_path))
        return -1

    app.logger.info('Processing data from {}'.format(data_path))
    first, second, name_prefix = split_identifier(map_id)

    path = os.path.join('cache', first)

    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except FileExistsError:
            pass

    path = os.path.join(path, second)

    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except FileExistsError:
            pass

    x, y, z = origin
    w, h = dimensions
    files = [os.path.join(data_path, f) for f in sorted(os.listdir(data_path)) if f.endswith('tif')]
    data = tifffile.imread(files[0])
    height, width = data.shape
    del data

    output_path += '/%05i.jpg'
    number = 16 * 16
    total = number * subsets
    xa = int(x * width)
    ya = int(y * height)
    slice_width = int(min(width - xa, w * width))
    slice_height = int(min(height - ya, h * height))

    parameters = dict(path=data_path, output=output_path,
                      x=xa, y=ya, za=int(z * len(files)),
                      w=slice_width, h=slice_height,
                      size=size, number=number, total=total)

    cmd = "ufo-launch read path={path} number={total} ! crop x={x} y={y} width={w} height={h} ! "

    if w == 1.0 and h == 1.0:
        cmd += "mask ! "

    cmd += "rescale width={size} height={size} ! map-slice number={number} ! write minimum=0 maximum=255 filename={output}"
    cmd = cmd.format(**parameters)

    output = subprocess.call(shlex.split(cmd))


@app.route('/maps', methods=['POST'])
def make_map():
    # authenticate for path access
    headers = {'Auth-Token': request.json['token']}
    url = '{}/datasets/{}/{}'.format(app.config['NOVA_API_URL'], request.json['user'], request.json['dataset'])
    r = requests.get(url, headers=headers)
    abort_for_status(r)

    # generate a unique map_id from the parameters
    origin = request.json.get('origin', [0.0, 0.0, 0.0])
    check_range(origin)

    dimensions = request.json.get('dimensions', [1.0, 1.0])
    check_range(dimensions)

    path = os.path.join(r.json()['path'], 'slices-corrected-axis_8bit')
    path = path if os.path.exists(path) else os.path.join(r.json()['path'], 'slices-8bit')
    path = path if os.path.exists(path) else os.path.join(r.json()['path'], 'slices_8bit')
    path = path if os.path.exists(path) else os.path.join(r.json()['path'], 'slices')

    subsets = request.json.get('subsets', 6)
    size = request.json.get('size', 256)
    identifier = "p={},o={},d={}".format(path, origin, dimensions)
    identifier = identifier.encode('utf-8')
    map_id = hashlib.sha256(identifier).hexdigest()

    args = (map_id, path, subsets, origin, dimensions, size)
    process = Process(target=create, args=args)
    process.start()
    jobs[map_id] = process

    response = jsonify()
    response.headers['location'] = url_for('check_queue', map_id=map_id)
    return response


@app.route('/maps/<map_id>')
@app.route('/maps/<map_id>/<subset>', methods=['GET'])
def get_map(map_id, subset=None):
    path = identifier_to_path(map_id)

    if not os.path.exists(path):
        abort(404)

    path += '/{:05}.jpg'.format(int(subset))

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


def get_local_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    return s.getsockname()[0]


def register(host):
    data = dict(name=SERVICE_NAME,
                url='http://{}:{}'.format(get_local_ip_address(), 5000),
                secret=SERVICE_SECRET)
    requests.post('/'.join((host, 'services')), data=data)


def shutdown(host):
    data = dict(secret=SERVICE_SECRET)
    requests.delete('/'.join((host, 'service', SERVICE_NAME)), data=data)


@app.route('/service')
def service():
    data = dict(status='running')
    return jsonify(data)


if __name__ == '__main__':
    register(app.config['NOVA_API_URL'])
    atexit.register(shutdown, app.config['NOVA_API_URL'])
    manager.run()
