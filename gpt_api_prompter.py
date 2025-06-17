import json
import logging
import os
from genie.testbed import load
from openai import OpenAI, OpenAIError


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    # filename="basic.log",
)


def connect_tb(tb_file):
    log.info(f'Loading testbed file "{tb_file}".')
    tb = load(tb_file)
    log.info("Connecting to testbed.")
    tb.connect(log_stdout=False)
    log.info("Successfully connected to testbed")

    return tb


def run_command(tb, dev, command):
    resp = tb.devices[dev].execute(command)

    return resp


def configure(tb):
    pass


def disconnect_tb(tb):
    log.info("Disconnecting from testbed, please wait.")
    tb.disconnect()
    log.info("Successfully disconnected from testbed.")


def prompt_gpt(user_input):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-4o",
        input=user_input,
    )

    return response


def get_prompt(filename):
    with open(filename, "r") as f:
        prompt = f.read()
    return prompt


def interact(tb):
    prompt = get_prompt("cisco_iosxe_prompt.txt")
    print("\nPress Ctrl-c to exit.\n")
    user_input = [{"role": "developer", "content": prompt}]
    while True:
        try:
            input_query = input("\n\n\tPrompt: ")
            user_input.append({"role": "user", "content": input_query})

            response = prompt_gpt(user_input)
            log.info(f"Reply from the LLM API: {response.output_text}")
            user_input.append(
                {"role": "assistant", "content": response.output_text}
            )

            reply = json.loads(response.output_text)
            if "answer" in reply.keys():
                continue

            command_resp = run_command(tb, "sr1-1", reply["command"])
            user_input.append(
                {
                    "role": "user",
                    "content": str(command_resp),
                }
            )

            response2 = prompt_gpt(user_input)
            reply2 = json.loads(response2.output_text)
            log.info(f"Reply from the LLM API: {reply2}")

            print(f"\n\t{reply2['answer']}\n")
        except KeyboardInterrupt:
            print()
            return
        except OpenAIError as e:
            log.exception(f"Caught OpenAIError: {e}.")
            return
        except Exception as e:
            log.exception(f"Caught exception: {e}")
            return


def main():
    tb = connect_tb("testbed.yaml")
    interact(tb)
    disconnect_tb(tb)


if __name__ == "__main__":
    main()
