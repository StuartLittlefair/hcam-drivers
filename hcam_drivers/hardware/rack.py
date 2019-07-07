# module to talk to the thermal enclosure
from hcam_widgets.gtc.corba import get_telescope_server


class GTCRackSensor(object):

    def temperature(self):
        s = get_telescope_server()
        return s.getCabinetTemperature1()

    def humidity(self):
        s = get_telescope_server()
        return s.getHumidity()
