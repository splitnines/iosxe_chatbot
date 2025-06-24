import json
import logging
import os
import platform
import pydoc
import re
import sys
from genie.testbed import load
from unicon.core.errors import (
    ConnectionError,
    SubCommandFailure,
    CredentialsExhaustedError,
)
from openai import OpenAI, OpenAIError
from lib.menu import menu


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="\033[90m%(asctime)s: %(levelname)s: %(message)s\033[0m",
    datefmt="%Y-%m-%d %H:%M:%S",
    # filename="basic.log",
)

# set the pager to be used
os.environ["PAGER"] = "more"


def handle_connect(tb_file):
    try:
        log.info(f'Loading testbed file "{tb_file}".')
        tb = load(tb_file)
        log.info("Connecting to testbed.")
        tb.connect(log_stdout=False, logfile=False)
        log.info("Successfully connected to testbed")

        return tb

    except CredentialsExhaustedError as e:
        log.error(f"Login failed: {e}")
        sys.exit(1)
    except ConnectionError as e:
        log.error(f"Failed to connect: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Caught exception {e}")
        sys.exit(1)


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


def log_total_tokens(total_tokens):
    print()
    log.info(f"Total tokens consumed for the session {total_tokens}")


def commit_change():
    operator_permission = input("Commit changes [y/n]: ")
    if operator_permission.lower() == "y":
        return True
    elif operator_permission.lower() == "n":
        return False
    else:
        return commit_change()


def user_cmd_parser(user_cmd_args):
    if user_cmd_args["user_input"] == "":
        return user_cmd_args

    # Start a new context window
    if user_cmd_args["input_query"].startswith("/n"):
        log.info("New context window started.\n")
        user_cmd_args["user_input"] = [
            {
                "role": "developer",
                "content": user_cmd_args["prompt"],
            }
        ]
        user_cmd_args["context_depth"] = 0

    # Display the developer prompt
    elif user_cmd_args["input_query"].startswith("/p"):
        print(user_cmd_args["prompt"])

    # Display the command menu
    elif user_cmd_args["input_query"].startswith("/m"):
        menu()

    # Reload the developer prompt
    elif user_cmd_args["input_query"].startswith("/r"):
        user_cmd_args["prompt"] = developer_input_prompt(
            user_cmd_args["prompt_file"]
        )
        log.info("Prompt reloaded.")
        log.info("New context window started.\n")
        user_cmd_args["user_input"] = [
            {
                "role": "developer",
                "content": user_cmd_args["prompt"],
            }
        ]
        user_cmd_args["context_depth"] = 0

    # Send a command to the device directly
    elif user_cmd_args["input_query"].startswith("/c"):
        parse_command_re = re.compile(r"^/c[omand\s]+(.+)")
        match = parse_command_re.search(user_cmd_args["input_query"])
        if match:
            command = match.group(1)
            command_resp = handle_command(
                user_cmd_args["testbed"], user_cmd_args["device"], command
            )
            print()
            pydoc.pager(command_resp)
            print()
            # print(command_resp, "\n")
        else:
            log.error("Could not parse the command.\n")

    # Quit the program
    elif user_cmd_args["input_query"].startswith("/q"):
        log_total_tokens(user_cmd_args["total_tokens"])
        handle_disconnect(user_cmd_args["testbed"])
        sys.exit(0)

    return user_cmd_args


def operator_prompt(chat_args):
    prompt = (
        f"┌──({chat_args['context_depth']})-"
        f"[{chat_args['device']}]-"
        "[IOS-XE Chatbot]"
    )
    print(prompt)
    operator_input = input("└─$ ")

    return operator_input


# LLM responses are in JSON format. Example:
# {"type": "response"}
# There are 3 types: command, answer and configure
def handle_iosxe_chat(tb, prompt_file):
    user_cmd_parser_args = {
        "testbed": tb,
        "device": "sr1-1",
        "context_depth": 0,
        "prompt_file": prompt_file,
        "total_tokens": 0,
        "prompt": developer_input_prompt(prompt_file),
    }

    token_count = 0

    menu()

    user_cmd_parser_args["user_input"] = [
        {"role": "developer", "content": user_cmd_parser_args["prompt"]}
    ]
    while True:
        try:
            user_cmd_parser_args["input_query"] = operator_prompt(
                user_cmd_parser_args
            )
            print()

            # parse the escaped commands from the user
            if (
                user_cmd_parser_args["input_query"].startswith("/")
                or user_cmd_parser_args["input_query"] == ""
            ):
                user_cmd_parser_args = user_cmd_parser(user_cmd_parser_args)
                continue

            #
            user_cmd_parser_args["user_input"].append(
                {
                    "role": "user",
                    "content": user_cmd_parser_args["input_query"],
                }
            )

            user_cmd_parser_args["context_depth"] += 1

            reply, token_count = handle_llm_prompt(
                user_cmd_parser_args["user_input"]
            )
            if reply == {}:
                log.error("Received an empty dict from handle_llm_prompt().")
                continue

            user_cmd_parser_args["total_tokens"] += token_count
            if "answer" in reply.keys():
                user_cmd_parser_args["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )
                # TODO: change to pager
                print(f"\n{reply['answer']}\n")
                continue

            elif "command" in reply.keys():
                user_cmd_parser_args["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )
                command_resp = handle_command(
                    user_cmd_parser_args["testbed"],
                    user_cmd_parser_args["device"],
                    reply["command"],
                )

                user_cmd_parser_args["user_input"].append(
                    {
                        "role": "user",
                        "content": str(command_resp),
                    }
                )

            reply, token_count = handle_llm_prompt(
                user_cmd_parser_args["user_input"]
            )
            if reply == {}:
                log.error("Received an empty dict from handle_llm_prompt().")
                continue

            user_cmd_parser_args["total_tokens"] += token_count
            if "answer" in reply.keys():
                print(f"\n{reply['answer']}\n")

                user_cmd_parser_args["user_input"].append(
                    {
                        "role": "assistant",
                        "content": str(reply),
                    }
                )
            elif "configure" in reply.keys():
                pydoc.pager("\n".join([line for line in reply["configure"]]))
                print()
                if commit_change() is False:
                    print("Discarding changes.\n")
                    continue

                conf_resp = handle_configure(
                    user_cmd_parser_args["testbed"],
                    user_cmd_parser_args["device"],
                    reply["configure"],
                )
                print(f"\n!\n{conf_resp}!\n")

        except OpenAIError as e:
            log.error(f"Caught OpenAIError: {e}.")
        except (json.JSONDecodeError, json.decoder.JSONDecodeError) as e:
            log.error(f"Caught JSONDecodeError: {e}")
        except Exception as e:
            log.error(f"Caught exception: {e}")


def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def main():
    clear_screen()
    tb_file = "testbed.yaml"
    if not os.path.exists(tb_file):
        log.error(f"File {tb_file} does not exist.")
        sys.exit(1)

    prompt_file = "iosxe_prompt.md"
    if not os.path.exists(prompt_file):
        log.error(f"File {prompt_file} does not exist.")
        sys.exit(1)

    tb = handle_connect(tb_file)

    try:
        total_tokens = handle_iosxe_chat(tb, prompt_file)
        log_total_tokens(total_tokens)
        handle_disconnect(tb)
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt....exiting.")
        handle_disconnect(tb)
    except Exception as e:
        log.error(f"Exception caught in main(): {e}")


if __name__ == "__main__":
    main()
