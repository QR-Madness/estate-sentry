"""
Sensors API: Manage/access sensor equipment.
"""
from flask import Blueprint, request

sensors_blueprint = Blueprint('EstateSentry:API:Sensors', __name__)


@sensors_blueprint.route('/sensor', methods=['GET', 'POST'])
def sensor():
    """
    Manages a registered, or available, sensor.
    """
    if request.method == 'GET':
        # TODO sensor data requested
        pass
    elif request.method == 'POST':
        # sensor create/update requested
        # TODO check if ID exists
        # TODO create sensor
        pass


@sensors_blueprint.route('/sensors', methods=['GET'])
def sensors():
    """
    Retrieves info about registered and available sensors.
    """
    # TODO get list of registered sensors
    if request.json.include_unregistered_sensors:
        # TODO get list of available unregistered sensors
        pass


@sensors_blueprint.route('/viewer/<sensor_id>', methods=['GET'])
def stream(sensor_id: str):
    """
    Streaming viewer of sensor data, can be used for CCTV, realtime, etc.
    :param sensor_id: Sensor ID
    :return: Streaming response
    """
    # TODO get sensor info, type, etc.
    # TODO get stream handler for sensor type
    # TODO transmit stream
    pass
