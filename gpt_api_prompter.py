import json
import logging
import os
import sys
from genie.testbed import load
from unicon.core.errors import ConnectionError
from openai import OpenAI, OpenAIError


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s: %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    # filename="basic.log",
)


def connect_tb(tb_file):
    try:
        log.info(f'Loading testbed file "{tb_file}".')
        tb = load(tb_file)
        log.info("Connecting to testbed.")
        tb.connect(log_stdout=False, logfile=False)
        log.info("Successfully connected to testbed")

    except ConnectionError as e:
        log.error(f"Failed to connect: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Caught exception {e}")
        sys.exit(1)

    return tb


def run_command(tb, dev, command):
    resp = tb.devices[dev].execute(command)

    return resp


# TODO: add code the to perform configuration tasks
def configure():
    pass


def disconnect_tb(tb):
    log.info("Disconnecting from testbed, please wait.")
    tb.disconnect()
    log.info("Successfully disconnected from testbed.")


def prompt_gpt(user_input):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model="gpt-4o",
            input=user_input,
        )

        return response

    except OpenAIError as e:
        log.error(f"Caught OpenAIError: {e}")
    except Exception as e:
        log.error(f"Caught exception: {e}")


def get_prompt(filename):
    with open(filename, "r") as f:
        prompt = f.read()
    return prompt


def iosxe_chat_loop(tb, prompt_file):
    prompt = get_prompt(prompt_file)

    print("\nPress Ctrl-c to exit.\n")
    print('Enter "/new" for a new context window.\n\n')

    user_input = [{"role": "developer", "content": prompt}]
    while True:
        try:
            input_query = input("Prompt: ")

            # Create a new context window
            if input_query == "/new":
                log.info("Starting new context window.")
                user_input = [{"role": "developer", "content": prompt}]
                input_query = input("Prompt: ")

            user_input.append({"role": "user", "content": input_query})

            response = prompt_gpt(user_input)
            if response is not None:
                log.info(f"Reply from the LLM API: {response.output_text}")
                user_input.append(
                    {"role": "assistant", "content": response.output_text}
                )

                reply = json.loads(response.output_text)
                if "answer" in reply.keys():
                    print(f"\n{reply['answer']}\n")
                    continue

                if "command" in reply.keys():
                    command_resp = run_command(tb, "sr1-1", reply["command"])
                    user_input.append(
                        {
                            "role": "user",
                            "content": str(command_resp),
                        }
                    )
                else:
                    log.error(
                        f"Reply did not contain a command: {reply['command']}"
                    )
                    continue

            response2 = prompt_gpt(user_input)
            if response2 is not None:
                reply2 = json.loads(response2.output_text)
                log.info(f"Reply from the LLM API: {reply2}")

                if "answer" in reply2.keys():
                    print(f"\n{reply2['answer']}\n")
                else:
                    log.info(f"Reply did not contain an answer {reply2}")
        except KeyboardInterrupt:
            print()
            return
        except OpenAIError as e:
            log.error(f"Caught OpenAIError: {e}.")
        except (json.JSONDecodeError, json.decoder.JSONDecodeError) as e:
            log.error(f"Caught JSONDecodeError: {e}")
        except Exception as e:
            log.error(f"Caught exception: {e}")


def main():
    tb_file = "testbed.yaml"
    if not os.path.exists(tb_file):
        log.error(f"File {tb_file} does not exist.")
        sys.exit(1)

    prompt_file = "cisco_iosxe_prompt.md"
    if not os.path.exists(prompt_file):
        log.error(f"File {prompt_file} does not exist.")
        sys.exit(1)

    tb = connect_tb(tb_file)
    iosxe_chat_loop(tb, prompt_file)
    disconnect_tb(tb)


if __name__ == "__main__":
    main()
