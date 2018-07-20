""" Mina Hållplatser API """
import datetime
from werkzeug.exceptions import HTTPException
import requests
from flask import Flask, jsonify, request

class NotFoundException(Exception):
    """ Exception to use when results are empty """
    pass

APP = Flask(__name__)

@APP.route('/')
def hello_world():
    """ Hello World """
    return 'Hello, World!'

@APP.route('/api/vasttrafik/gps', methods=['POST'])
def get_nearby_stops():
    """ GPS """
    APP.logger.info('get_nearby_stops():')

    try:
        data = request.get_json()
        latitude = data['latitude']
        longitude = data['longitude']
        access_token = request.headers['access_token']

        url = 'https://api.vasttrafik.se/bin/rest.exe/v2/location.nearbystops?originCoordLat='\
            + str(latitude) + '&originCoordLong=' + str(longitude) + '&format=json'
        headers = {'Authorization': 'Bearer ' + access_token}
        req = requests.get(url, headers=headers)
        if req.status_code != 200:
            raise HTTPException(description=req.json())
        json = req.json()
        location_list = json['LocationList']
        if 'StopLocation' not in location_list:
            raise NotFoundException('Did not find anything')
        response = location_list['StopLocation']
        filtered = [item for item in response if 'track' not in item]

        return jsonify({
            'data': filtered,
            'timestamp': datetime.date.today()
        })
    except HTTPException as err:
        return make_error(500, err.description)
    except NotFoundException as err:
        return make_error(404, str(err))

def make_error(status_code, message):
    """ Function for returning errors easily """
    response = jsonify({
        'status': status_code,
        'message': message,
    })
    response.status_code = status_code
    return response

APP.run(port=5000, debug=True)
