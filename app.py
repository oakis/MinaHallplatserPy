""" Mina Hållplatser API """
import logging
from datetime import date, datetime
import math
from itertools import groupby
from werkzeug.exceptions import HTTPException
import requests
from flask import Flask, jsonify, request

APP = Flask(__name__)

if __name__ != '__main__':
    GUNICORN_LOGGER = logging.getLogger('gunicorn.error')
    APP.logger.handlers = GUNICORN_LOGGER.handlers
    APP.logger.setLevel(GUNICORN_LOGGER.level)

class NotFoundException(Exception):
    """ Exception to use when results are empty """
    pass

@APP.route('/')
def hello_world():
    """ Hello World """
    return 'Hello, World!'

@APP.route('/api/vasttrafik/departures', methods=['POST'])
def get_departures(time_span='90'):
    """ Departures """
    APP.logger.info('get_departures():')

    try:
        data = request.get_json()
        id_number = data['id']
        current_date = date.today().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M')
        access_token = request.headers['access_token']

        url = 'https://api.vasttrafik.se/bin/rest.exe/v2/departureBoard?id='\
            + id_number + '&date=' + current_date + '&time=' + current_time +\
            '&format=json&timeSpan=' + time_span + '&maxDeparturesPerLine=2&needJourneyDetail=0'
        headers = {'Authorization': 'Bearer ' + access_token}
        req = requests.get(url, headers=headers)
        json = req.json()
        departure_board = json['DepartureBoard']
        if 'error' in departure_board:
            error = departure_board['error']
            if error == 'No journeys found':
                return get_departures('1440')
            raise NotFoundException('Hittade inga avgångar på denna hållplats.')

        if isinstance(departure_board['Departure'], dict):
            departures = [departure_board['Departure']]
        else:
            departures = departure_board['Departure']

        def departures_model(item):

            def get_key_value(key):
                return item[key] if key in item else None

            is_live = 'rtTime' in item
            if is_live:
                current_time = get_key_value('rtTime')
                current_date = get_key_value('rtDate')
            else:
                current_time = get_key_value('time')
                current_date = get_key_value('date')

            direction = get_key_value('direction')
            via = ''
            if 'via' in direction:
                direction, via = direction.split('via')

            time_departure = datetime.strptime(current_date + ' ' + current_time, '%Y-%m-%d %H:%M')
            time_now = datetime.now()
            diff = time_departure - time_now
            if time_now >= time_departure:
                minutes_left = 0
            else:
                minutes_left = math.floor(((diff).seconds) / 60)
            clock_left = item['rtTime'] if is_live else item['time']

            return dict({
                'accessibility': get_key_value('accessibility'),
                'bgColor': get_key_value('bgColor'),
                'clockLeft': clock_left,
                'clockNext': None,
                'timeLeft': minutes_left,
                'timeNext': None,
                'direction': direction.strip(),
                'via': 'via ' + via.strip() if via != '' else via,
                'name': get_key_value('name'),
                'sname': get_key_value('sname'),
                'type': get_key_value('type'),
                'journeyid': get_key_value('journeyid'),
                'track': get_key_value('track'),
                'fgColor': get_key_value('fgColor'),
                'isLive': is_live,
            })

        mapped_departures = sorted(
            list(map(departures_model, departures)),
            key=lambda x: (x["name"], x["direction"])
        )

        def merge_departures(departure_list):
            for (bus), busses in groupby(departure_list, key=lambda x: (x["name"], x["direction"])):
                grouped_busses = list(busses)
                times = [bus["timeLeft"] for bus in grouped_busses]
                clocks = [bus["clockLeft"] for bus in grouped_busses]
                yield {
                    **grouped_busses[0],
                    "timeLeft": min(times, key=int),
                    "timeNext": None if len(times) == 1 else max(times, key=int),
                    "clockLeft": min(clocks),
                    "clockNext": None if len(clocks) == 1 else max(clocks),
                }

        merged_departures = list(merge_departures(mapped_departures))

        return jsonify({
            'departures': merged_departures,
            'timestamp': date.today().strftime('%Y-%m-%d') + 'T'\
                + datetime.now().strftime('%H:%M:%S'),
        })
    except HTTPException as err:
        return make_error(500, err.description)
    except NotFoundException as err:
        return make_error(404, str(err))


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
            raise NotFoundException('Kunde inte hitta några hållplatser nära dig.')
        response = location_list['StopLocation']
        filtered = [item for item in response if 'track' not in item]

        return jsonify({
            'data': filtered,
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


@APP.route('/api/vasttrafik/stops', methods=['POST'])
def search_stops():
    """ Search stops """
    APP.logger.info('search_stops():')

    try:
        data = request.get_json()
        search_string = str(data['search'])
        access_token = request.headers['access_token']

        url = 'https://api.vasttrafik.se/bin/rest.exe/v2/location.name?input='\
            + search_string + '&format=json'
        headers = {'Authorization': 'Bearer ' + access_token}
        req = requests.get(url, headers=headers)
        if req.status_code != 200:
            raise HTTPException(description=req.json())
        json = req.json()

        location_list = json['LocationList']
        if 'StopLocation' in location_list:
            if isinstance(location_list['StopLocation'], dict):
                stops = [location_list['StopLocation']]
            else:
                stops = location_list['StopLocation']
        else:
            raise NotFoundException('Hittade inga hållplatser. Prova att söka på något annat.')

        def search_model(stop):
            return dict({
                'id': stop['id'],
                'name': stop['name'],
            })

        mapped_stops = list(map(search_model, stops))

        return jsonify({
            'data': mapped_stops[0:10],
            'timestamp': date.today().strftime('%Y-%m-%d') + 'T'\
                + datetime.now().strftime('%H:%M:%S'),
        })
    except HTTPException as err:
        return make_error(500, err.description)
    except NotFoundException as err:
        return make_error(404, str(err))

if __name__ == '__main__':
    APP.run(port=5000, debug=True)
