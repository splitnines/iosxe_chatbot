import datetime as dt
import difflib
import logging
import openai
import os
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
    def prompt_gpt(self):
        try:
            openai.api_key = os.getenv("OPENAI_API_KEY")
            if not openai.api_key:
                self.failed(
                    "Missing OPENAI_API_KEY enviroment variable.",
                    goto=["common_cleanup"],
                )

            try:
                with open("prompt.txt", "r") as f:
                    self.prompt = f.read()

            except OSError as e:
                self.failed(
                    f"Failed to read prompt.txt: {e}", goto=["common_cleanup"]
                )

            log.info(f"ChatGPT prompt:\n\n{self.prompt}")
            log.info("")

            uploaded_file = None
            try:
                uploaded_file = openai.files.create(
                    file=open("sr1-1_running-config.pdf", "rb"),
                    purpose="assistants",
                )
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": self.prompt,
                                    },
                                    {
                                        "type": "file",
                                        "file": {"file_id": uploaded_file.id},
                                    },
                                ],
                            }
                        ],
                    )

                    self.gpt_config = response.choices[0].message.content
                except openai.OpenAIError as e:
                    self.failed(
                        f"OpenAI API request failed: {e}",
                        goto=["common_cleanup"],
                    )
            except OSError as e:
                self.failed(
                    f"Failed to open PDF file: {e}", goto=["common_cleanup"]
                )
            except openai.OpenAIError as e:
                self.failed(
                    f"Failed to upload file to OpenAI: {e}",
                    goto=["common_cleanup"],
                )

            if not uploaded_file or not hasattr(uploaded_file, "id"):
                self.failed(
                    "File upload failed; uploaded_file is None",
                    goto=["common_cleanup"],
                )

            log.info(f"ChatGPT config:\n\n{self.gpt_config}")
            log.info("")
        except Exception as e:
            self.failed(f"Unhandled exception: {e}", goto=["common_cleanup"])

    @aetest.test
    def capture_show_run(self):
        self.pre_change = self.device.execute("show running-config")

    @aetest.test
    def config_change(self):
        self.device.configure(self.gpt_config)

    @aetest.test
    def recapture_show_run(self):
        self.post_change = self.device.execute("show running-config")

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
