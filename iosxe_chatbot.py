import json
import logging
import os
import sys
from genie.testbed import load
from unicon.core.errors import (
    ConnectionError,
    SubCommandFailure,
    CredentialsExhaustedError,
)
from openai import OpenAI, OpenAIError


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s: %(levelname)s: %(message)s\033[0m",
    datefmt="%Y-%m-%d %H:%M:%S",
    # filename="basic.log",
)


def handle_connect(tb_file):
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


def handle_command(tb, dev, command):
    resp = tb.devices[dev].execute(command)
    return resp


def handle_configure(tb, dev, conf_list):
    try:
        resp = tb.devices[dev].configure(conf_list)
        log.info(f"Device {dev} configured successully.")
        return resp
    except SubCommandFailure as e:
        log.error(f"Device {dev} configuration failed: {e}")
    except Exception as e:
        log.error(f"Caught generic exception: {e}")


def handle_disconnect(tb):
    log.info("Disconnecting from testbed, please wait.")
    tb.disconnect()
    log.info("Successfully disconnected from testbed.")


def handle_llm_prompt(user_input):
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model="gpt-4o",
            input=user_input,
        )
        if response is not None:
            total_tokens = 0
            if response.usage is not None:
                log.info(f"Total Tokens: {response.usage.total_tokens}")
                total_tokens += response.usage.total_tokens

            log.info(f"Reply from the LLM API: {response.output_text}")

            reply = json.loads(response.output_text)

            return reply, total_tokens

    except OpenAIError as e:
        log.error(f"Caught OpenAIError: {e}")
    except Exception as e:
        log.error(f"Caught exception: {e}")

    return {}, 0


def developer_input_prompt(filename):
    with open(filename, "r") as f:
        prompt = f.read()
    return prompt


def menu():
    print("\nPress Ctrl-c to exit.\n")
    print('Enter "/new" for a new context window.')
    print('Enter "/menu" to print this menu.')
    print('Enter "/prompt" to print the developer prompt.\n\n')


def log_total_tokens(total_tokens):
    print()
    log.info(f"Total tokens consumed for the session {total_tokens}")


# LLM responses are in JSON format. Example:
# {"type": "response"}
# There are 3 types: command, answer and configure
def handle_iosxe_chat(tb, prompt_file):
    context_depth = 0
    token_count = 0
    prompt = developer_input_prompt(prompt_file)

    menu()

    user_input = [{"role": "developer", "content": prompt}]
    while True:
        try:
            input_query = input(f"[{context_depth}]Prompt: ")
            print()

            # handle user commands
            match input_query:
                # create a new context window
                case "/new":
                    log.info("Starting new context window.\n")
                    user_input = [{"role": "developer", "content": prompt}]
                    context_depth = 0
                    continue
                # display the developer prompt
                case "/prompt":
                    print(prompt)
                    continue
                # display the menu
                case "/menu":
                    menu()
                    continue
                # don't send empty commands to the LLM
                case "":
                    continue

            user_input.append({"role": "user", "content": input_query})

            context_depth += 1

            reply, total_tokens = handle_llm_prompt(user_input)
            if reply == {}:
                log.error("Received an empty dict from handle_llm_prompt().")
                continue

            token_count += total_tokens
            if "answer" in reply.keys():
                user_input.append({"role": "assistant", "content": str(reply)})
                print(f"\n{reply['answer']}\n")
                continue

            elif "command" in reply.keys():
                user_input.append({"role": "assistant", "content": str(reply)})
                command_resp = handle_command(tb, "sr1-1", reply["command"])

                user_input.append(
                    {
                        "role": "user",
                        "content": str(command_resp),
                    }
                )

            reply, total_tokens = handle_llm_prompt(user_input)
            if reply == {}:
                log.error("Received an empty dict from handle_llm_prompt().")
                continue

            token_count += total_tokens
            if "answer" in reply.keys():
                print(f"\n{reply['answer']}\n")

                user_input.append(
                    {
                        "role": "assistant",
                        "content": str(reply),
                    }
                )
            elif "configure" in reply.keys():
                conf_resp = handle_configure(tb, "sr1-1", reply["configure"])
                print(f"\n!\n{conf_resp}!\n")

        except KeyboardInterrupt:
            return token_count
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

    tb = handle_connect(tb_file)
    total_tokens = handle_iosxe_chat(tb, prompt_file)
    log_total_tokens(total_tokens)
    handle_disconnect(tb)


if __name__ == "__main__":
    main()
