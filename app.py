""" Mina Hållplatser API """
import datetime
import requests
from flask import Flask, jsonify, request

APP = Flask(__name__)

@APP.route('/')
def hello_world():
    """ Hello World """
    return 'Hello, World!'

@APP.route('/api/vasttrafik/gps', methods=['POST'])
def get_nearby_stops():
    """ GPS """
    APP.logger.info('get_nearby_stops():')

    data = request.get_json()
    latitude = data['latitude']
    longitude = data['longitude']
    access_token = request.headers['access_token']

    url = 'https://api.vasttrafik.se/bin/rest.exe/v2/location.nearbystops?originCoordLat='\
          + str(latitude) + '&originCoordLong=' + str(longitude) + '&format=json'
    headers = {'Authorization': 'Bearer ' + access_token}
    req = requests.get(url, headers=headers)
    response = req.json()['LocationList']['StopLocation']
    filtered = [item for item in response if 'track' not in item]

    return jsonify({
        'data': filtered,
        'timestamp': datetime.date.today()
    })

APP.run(port=5000, debug=True)
