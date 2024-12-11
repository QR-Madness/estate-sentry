"""
Sensors API: Manage/access sensor equipment.
"""
from flask import Blueprint, request

auth_blueprint = Blueprint('EstateSentry:API:Sensors', __name__)


@auth_blueprint.route('/sensor', methods=['GET', 'POST'])
def sensor():
    """
    Retrieves info about a registered sensor.
    """
    if request.method == 'GET':
        # TODO sensor data requested
        pass
    elif request.method == 'POST':
        # sensor create/update requested
        # TODO check if ID exists
        # TODO create sensor
        pass


@auth_blueprint.route('/cctv/<camera_id>', methods=['GET'], defaults={'camera_id': None})
def cctv(camera_id: str):
    """
    View a CCTV feed of a camera sensor.
    :param camera_id: Sensor ID of camera.
    """
    pass


@auth_blueprint.route('/sensors', methods=['GET'])
def sensors():
    """
    Retrieves info about current and available sensors.
    """
    # TODO get list of registered sensors
    if request.json.include_unregistered_sensors:
        # TODO get list of available unregistered sensors
        pass
