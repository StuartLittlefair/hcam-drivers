from __future__ import absolute_import, unicode_literals, print_function, division
import requests
import time
import json
import numpy as np

THINGSBOARD_URL = 'https://ph1splrasppi2.ddns.shef.ac.uk'

DEVICE_ACCESS_TOKENS = dict(
    ccd1='WCFoIo4k8sabbTKc1BRC',
    ccd2='QSf6FQCuwmyX0jUb4v1e',
    ccd3='pI8RJk1IClNn98O1NhhP',
    ccd4='jFfZF2IfhB1n6SIXIFDP',
    ccd5='KAOB2pRmGjOVhA421wMl',
    ngc='kOedychrCWKTafS26FA8',
    compo='WcPuVWxdi14WRiFRkBmT',
    rack='krW8pzydOnrYOWAfEMnZ',
    chiller='zqaSv57Kl9L6KA4i9OuQ',
    slide='d1PSa7DfrPHj7YoUl6BS'
)

ALLOWED_PROPERTIES = dict(
    ngc=['flow'],
    rack=['temperature', 'humidity'],
    chiller=['temperature'],
    slide=['position'],
    compo=['injection.angle', 'pickoff.angle', 'slide.position'],
)
for i in range(1, 6):
    ALLOWED_PROPERTIES['ccd' + str(i)] = ['temperature', 'flow',
                                          'pressure', 'current',
                                          'heatsink',
                                          'peltier.status']


def upload_telemetry(device, data):
    device = device.lower()
    allowed_properties = ALLOWED_PROPERTIES[device]
    for key in data:
        if key not in allowed_properties:
            raise ValueError(
                'property {} is not allowed for device {}'.format(key, device)
            )

    # package timestamp
    data = {'values': data}
    data['ts'] = int(round(time.time() * 1000))

    headers = {'Content-Type': 'application/json'}
    ACCESS_TOKEN = DEVICE_ACCESS_TOKENS.get(device)
    if ACCESS_TOKEN is None:
        raise ValueError('unrecognised device {}'.format(device))
    url = '{}/api/v1/{}/telemetry'.format(
        THINGSBOARD_URL, ACCESS_TOKEN
    )
    response = requests.post(url, data=json.dumps(data), headers=headers)
    response.raise_for_status()


def fake_data():
    means = {
        'temperature': -90,
        'flow': 1.0,
        'pressure': 1e-05,
        'current': 10,
        'humidity': 15,
        'peltier.status': 0,
        'heatsink': 15,
        'injection.angle': 45,
        'pickoff.angle': -45,
        'position': 1000
    }
    try:
        while True:
            for dev in DEVICE_ACCESS_TOKENS.keys():
                props = ALLOWED_PROPERTIES[dev]
                data = {prop: means[prop] * (1+np.random.normal(scale=0.05)) for prop in props}
                if 'peltier.status' in data:
                    data['peltier.status'] = 'OK'
                if dev == 'chiller' or dev == 'rack':
                    data['temperature'] = 10 * (1+np.random.normal(scale=0.05))
                yield (dev, data)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    it = fake_data()
    try:
        while True:
            dev, data = next(it)
            print(f'Uploading data to {dev}')
            try:
                upload_telemetry(dev, data)
            except Exception as err:
                print(f'failed: {err}')
            time.sleep(.1)
    except KeyboardInterrupt:
        pass
