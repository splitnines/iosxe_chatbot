import logging
from pyats import aetest
from pyats.log.utils import banner
from genie.metaparser.util.exceptions import SchemaEmptyParserError

log = logging.getLogger(__name__)
log.info(banner("pyATS TDD Automated Network Testing"))

WORKING_DIR = "/home/rickey/Scripts/python/pyats/"


class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        """Connect to all the devices"""
        testbed.connect(log_stdout=False)

    @aetest.subsection
    def loop_mark(self, testbed):
        aetest.loop.mark(TestGenericConfig, device_name=testbed.devices)


class TestGenericConfig(aetest.Testcase):
    @aetest.test
    def setup(self, testbed, device_name):
        self.device = testbed.devices[device_name]

    @aetest.test
    def global_config_change(self):
        self.device.configure("cdp run")

    @aetest.test
    def interface_config_change(self):
        self.interfaces = self.device.parse("show ip interface brief")
        for interface in self.interfaces["interface"]:
            if "Ethernet" in interface:
                log.info(f"Adding CDP to interface {interface}")
                self.device.configure(f"interface {interface}\ncdp enable")

    @aetest.test
    def verify_global_config_change(self):
        try:
            show_cdp = self.device.parse("show cdp")
            if show_cdp.get("cdpv2") == "enabled":
                self.passed()
        except SchemaEmptyParserError:
            self.failed(f"CDP is not running on {self.device.name}")

    @aetest.test
    def verify_interface_config_change(self):
        cdp_failed_list = []
        try:
            cdp_interfaces = self.device.parse("show cdp interface")
            for interface in self.interfaces["interface"]:
                if "Ethernet" in interface:
                    if interface not in cdp_interfaces["interface"].keys():
                        cdp_failed_list.append(interface)
            if len(cdp_failed_list) > 0:
                self.failed(
                    f"CDP not enabled on {self.device.name} interface"
                    f"{', '.join(cdp_failed_list)}"
                )
            else:
                self.passed()
        except SchemaEmptyParserError:
            self.failed(f"CDP not enabled on {self.device.name}")


class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_from_devices(self, testbed):
        testbed.disconnect()


if __name__ == "__main__":
    aetest.main
