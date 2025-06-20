import json
import logging
import os
import sys
from genie.testbed import load
from unicon.core.errors import ConnectionError, SubCommandFailure
from openai import OpenAI, OpenAIError


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s: %(levelname)s: %(message)s\033[0m",
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


def configure(tb, dev, conf_list):
    try:
        tb.devices[dev].configure(conf_list)
        log.info(f"Device {dev} configured successully.")
    except SubCommandFailure as e:
        log.error(f"Device {dev} configuration failed: {e}")
    except Exception as e:
        log.error(f"Caught generic exception: {e}")


def disconnect_tb(tb):
    print()
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


def menu():
    print("\nPress Ctrl-c to exit.\n")
    print('Enter "/new" for a new context window.')
    print('Enter "/menu" to print this menu.')
    print('Enter "/prompt" to print the developer prompt.\n\n')


# LLM responses are in JSON format. Example:
# {"type": "response"}
# There are 3 types: command, answer and configure
def iosxe_chat_loop(tb, prompt_file):
    context_depth = 0
    prompt = get_prompt(prompt_file)

    menu()

    user_input = [{"role": "developer", "content": prompt}]
    while True:
        try:
            input_query = input(f"[{context_depth}]Prompt: ")
            print()

            # Create a new context window
            if input_query == "/new":
                log.info("Starting new context window.\n")
                user_input = [{"role": "developer", "content": prompt}]

                context_depth = 0
                continue

            # Print the developer prompt to the screen
            if input_query == "/prompt":
                print(prompt)
                continue

            if input_query == "/menu":
                menu()
                continue

            # Don't send empty prompts
            if input_query == "":
                continue

            user_input.append({"role": "user", "content": input_query})

            context_depth += 1

            response = prompt_gpt(user_input)
            if response is not None:
                if response.usage is not None:
                    log.info(
                        f"Total Tokens: {response.usage.total_tokens}"
                    )

                log.info(f"Reply from the LLM API: {response.output_text}")

                reply = json.loads(response.output_text)

                if "answer" in reply.keys():
                    user_input.append(
                        {"role": "assistant", "content": response.output_text}
                    )
                    print(f"\n{reply['answer']}\n")
                    continue

                elif "command" in reply.keys():
                    user_input.append(
                        {"role": "assistant", "content": response.output_text}
                    )
                    command_resp = run_command(tb, "sr1-1", reply["command"])

                    user_input.append(
                        {
                            "role": "user",
                            "content": str(command_resp),
                        }
                    )

                    response = prompt_gpt(user_input)
                    if response is not None:
                        if response.usage is not None:
                            log.info(
                                f"Total Tokens: {response.usage.total_tokens}"
                            )

                        reply = json.loads(response.output_text)

                        log.info("Reply from the LLM API: {reply}")
                        if "answer" in reply.keys():
                            print(f"\n{reply['answer']}\n")

                            user_input.append(
                                {
                                    "role": "assistant",
                                    "content": response.output_text,
                                }
                            )
                        else:
                            log.error(
                                f"Reply did not contain an answer {reply}"
                            )
                elif "configure" in reply.keys():
                    configure(tb, "sr1-1", reply['configure'])

        except KeyboardInterrupt:
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
