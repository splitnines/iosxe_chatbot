import datetime as dt
import difflib
import logging

# import openai
import os
from openai import OpenAI, OpenAIError
from pyats import aetest
from pyats.log.utils import banner
# from genie.utils.diff import Diff


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    # filename="basic.log",
)
log.info(banner("ChatGPTConfigOps"))


class common_setup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        testbed.connect(log_stdout=False)

    @aetest.subsection
    def loop_mark(self, testbed):
        aetest.loop.mark(ChatGPTConfigOps, device_name=testbed.devices)


class ChatGPTConfigOps(aetest.Testcase):
    @aetest.test
    def setup(self, testbed, device_name):
        self.device = testbed.devices[device_name]

    @aetest.test
    def capture_show_run(self):
        self.pre_change = self.device.execute("show running-config brief")

    @aetest.test
    def prompt_gpt(self):
        try:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            if not client:
                self.failed(
                    "Failed to initialize OpenAI client.",
                    goto=["common_cleanup"],
                )
            try:
                with open("prompt.txt", "r") as f:
                    self.prompt = f.read()
            except OSError as e:
                self.failed(
                    f"Failed to read prompt.txt: {e}", goto=["common_cleanup"]
                )

            self.input = self.prompt + "\n\n" + self.pre_change

            try:
                self.gpt_config = client.responses.create(
                    model="gpt-4o", input=self.input
                )
            except OpenAIError as e:
                self.failed(f"Failed to get a response from openai: {e}")

            log.info(f"ChatGPT prompt:\n\n{self.prompt}")
            log.info("")

            log.info(f"ChatGPT config:\n\n{self.gpt_config.output_text}")
            log.info("")
        except Exception as e:
            self.failed(f"Unhandled exception: {e}", goto=["common_cleanup"])

    @aetest.test
    def config_change(self):
        self.device.configure(self.gpt_config.output_text)

    @aetest.test
    def recapture_show_run(self):
        self.post_change = self.device.execute("show running-config brief")

    @aetest.test
    def show_run_diff(self):
        if self.pre_change is None:
            self.failed(
                "Failed: self.pre_change is None", goto=["common_cleanup"]
            )
        if self.post_change is None:
            self.failed(
                "Failed: self.post_change is None", goto=["common_cleanup"]
            )

        diff = difflib.ndiff(
            self.pre_change.splitlines(), self.post_change.splitlines()
        )

        show_run_diff_output = "\n".join(
            line
            for line in diff
            if line.startswith("-") or line.startswith("+")
        )

        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        file = f"running-config_diff_{timestamp}.log"
        try:
            with open(file, "w") as f:
                f.write(show_run_diff_output)
        except OSError as e:
            self.failed(f"Failed to write file {file}: {e}")


class common_cleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_from_devices(self, testbed):
        testbed.disconnect()
