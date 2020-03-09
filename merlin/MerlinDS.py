# Device library import
from .Merlin import Merlin

# Tango imports
from tango import AttrWriteType, DispLevel, DevState
from tango.server import Device, DeviceMeta, attribute, command, server_run,  device_property

import numpy as np

class MerlinDS(Device):
    """ A Merlin Tango device.

        Device States Description:

        DevState.ON :     The device is in operation
        DevState.INIT :   Initialisation of the communication with the device and initial configuration
        DevState.FAULT :  The Device has a problem and cannot handle further requests.
        DevState.MOVING : The Device is engaged in an acquisition.
    """

    # Properties
    Host = device_property(dtype=str, default_value='b303a-a100384-dia-detpicu-02.maxiv.lu.se', doc="hostname")
    DataPort = device_property(dtype=int, default_value=6342)
    CommandPort = device_property(dtype=int, default_value=6341)

    # Commands
    @command()
    def startacquisition(self):
        self.merlin.send_command('STARTACQUISITION')

    @command()
    def stopacquisition(self):
        self.merlin.send_command('STOPACQUISITION')

    @command()
    def softtrigger(self):
        self.merlin.send_command('SOFTTRIGGER')

    @command()
    def reset(self):
        self.merlin.send_command('RESET')

    # Attributes
    @attribute(label='operating energy', dtype=int, doc='photon energy (keV)')
    def energy(self):
        return self.merlin.get_prop('OPERATINGENERGY')

    @energy.write
    def energy(self, val):
        self.merlin.set_prop('OPERATINGENERGY', val)

    # Device methods
    def init_device(self):
        """Instantiate device object, do initial instrument configuration."""
        self.set_state(DevState.INIT)
        
        try:
            self.get_device_properties()
            self.merlin = Merlin(host=self.Host, cmd_port=self.CommandPort, dat_port=self.DataPort)
            self.set_state(DevState.ON)
        
        except Exception as e:
            self.set_state(DevState.FAULT)
            self.set_status('Device failed at init: %s' % e)

    # This sets the state before every command
    def always_executed_hook(self):
        if self.get_state() == DevState.MOVING:
            # check the detector here to see if we should update the state
            pass

def main():
    server_run((MerlinDS,))

if __name__ == "__main__":
    main()

