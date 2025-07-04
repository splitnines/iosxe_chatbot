import json
import os
import platform
import pydoc
import re
import readline
import sys
from time import sleep
from lib.menu import menu
from lib.logs import logger
from openai import OpenAI, OpenAIError
from socket import error as s_error
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetMikoTimeoutException,
    NetMikoAuthenticationException,
    ConfigInvalidException,
    ConnectionException,
)


# set the logging
log = logger("info")

# set the pager to be used
os.environ["PAGER"] = "more"


def readline_input(prompt=""):
    try:
        return input(prompt)
    except EOFError:
        return ""


def handle_command_line_args():
    usage = "python iosxe_chatbot.py <device IP/name"
    if len(sys.argv) != 2:
        print(usage, file=sys.stderr)
        sys.exit(1)

    return sys.argv[1]


def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def developer_input_prompt(filename):
    with open(filename, "r") as f:
        prompt = f.read()
    return prompt


def ios_prompt(conn):
    return conn.find_prompt()


def log_total_tokens(total_tokens):
    print()
    log.info(f"Total tokens consumed for the session {total_tokens}")


def commit_change():
    operator_permission = readline_input("Commit changes [y/n]: ")
    if operator_permission.lower() == "y":
        return True
    elif operator_permission.lower() == "n":
        return False
    else:
        return commit_change()


def operator_prompt(operator_prompt_params):
    prompt = f"┌──({operator_prompt_params['context_depth']})-[IOS-XE Chatbot]"
    device_prompt = ios_prompt(operator_prompt_params["conn"])
    print(prompt)
    operator_input = readline_input(f"└─ {device_prompt} ")

    return operator_input


def handle_connect(device_params):
    """
    Establishes a connection to a network device using the provided device
    parameters.

    Parameters: device_params (dict): A dictionary containing the following
    keys:
        - host (str): The hostname or IP address of the device.
        - username (str): The username for authentication.
        - password (str): The password for authentication.

    Returns: ConnectHandler: A connection object representing the connection to
    the device.

    Raises:
    NetMikoAuthenticationException: If authentication fails for the device.
    ConnectionException: If a general connection exception occurs.
    NetMikoTimeoutException: If a timeout occurs during the connection attempt.
    Exception: For any other unhandled exceptions that may occur.

    Example:
    device_params = {
        "host": "192.168.1.1",
        "username": "admin",
        "password": "password123"
    }
    connection = handle_connect(device_params)
    """

    try:
        conn = ConnectHandler(
            host=device_params["host"],
            port=22,
            username=device_params["username"],
            password=device_params["password"],
            device_type="cisco_ios",
            timeout=10,
        )

        return conn

    except NetMikoAuthenticationException as e:
        log.error(f"Authentication failed for {device_params['host']}: {e}")
        sys.exit(1)
    except ConnectionException as e:
        log.error(f"ConnectionException for {device_params['host']}: {e}")
        sys.exit(1)
    except NetMikoTimeoutException as e:
        log.error(f"TimeoutException for {device_params['host']}: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(
            "Unhandled exception during connection for "
            f"{device_params['host']}: {e}"
        )
        sys.exit(1)


def handle_command(conn, command):
    """
    Sends a command to a connection object and returns the response.

    Parameters:
    conn (Connection): A connection object to send the command to.
    command (str): The command to be sent.

    Returns:
    str: The response received after sending the command.

    Raises:
    ValueError: If the command does not end with a question mark ('?').

    This function first checks if the command ends with a question mark ('?').
    If it does, it sends the command to the connection object and returns the
    response after removing the command from it. If the command does not end
    with a question mark, it sends the command to the connection object and
    returns the response.

    The response is obtained by sending the command to the connection object
    and expecting a prompt or question mark at the end of the response. The
    prompt or question mark is stripped from the response before returning it.
    """

    if re.search(r".+\?$", command):
        conn.write_channel(command + "\n")
        sleep(0.1)
        resp = conn.read_channel()
        return resp.replace(command, "")

    expect_re = re.compile(r"[#>?:]\s*$")
    resp = conn.send_command(
        command_string=command,
        expect_string=expect_re,
        strip_prompt=True,
        strip_command=True,
    )

    return resp


def handle_configure(conn, conf_list):
    """
    Configure a network device using a list of configuration commands.

    Parameters:
    conn (connection): A connection object to the network device.
    conf_list (list): A list of configuration commands to be sent to the
                      device.

    Returns:
    str: Response from the device after sending the configuration commands.

    Raises:
    ConfigInvalidException: If the configuration provided is invalid.
    Exception: If any other error occurs during the configuration process.
    """
    try:
        resp = conn.send_config_set(conf_list)
        log.info("Configuration successully.")
        return resp
    except ConfigInvalidException as e:
        log.error(f"ConfigInvalidException: {e}")
    except Exception as e:
        log.error(f"Unhandled exception in handle_configure(): {e}")


def handle_disconnect(conn, host):
    """
    Handles the disconnection of a connection to a host.

    Parameters:
    conn (Connection): The connection object to be disconnected.
    host (str): The hostname or IP address of the host being disconnected from.

    Returns:
    None

    Raises:
    None
    """
    conn.disconnect()
    log.info(f"Connection to {host} closed.")


def handle_llm_api(user_input):
    """
    Calls the OpenAI API with the given user input and returns the response
    along with the total number of tokens used.

    Parameters:
    user_input (str): The input text to be sent to the OpenAI API.

    Returns:
    tuple: A tuple containing a dictionary representing the response from the
    OpenAI API and an integer representing the total number of tokens used.

    Raises:
    OpenAIError: If an error occurs while calling the OpenAI API.
    Exception: If any other unexpected error occurs.

    Example:
    handle_llm_api("Hello, how are you?")
    """
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
        log.error(f"OpenAIError: {e}")
    except Exception as e:
        log.error(f"Unhandled exception in handle_llm_api(): {e}")

    return {}, 0


def operator_cmds(operator_cmd_params):
    """
    Process operator commands based on user input.

    Parameters:
    operator_cmd_params (dict): A dictionary containing various parameters like
    user input, input query, prompt, context depth, etc.

    Returns:
    dict: Updated operator command parameters after processing the user input.

    Raises:
    ValueError: If the input query does not match any known command.

    This function processes different operator commands based on the user input
    provided. It checks the input query and performs specific actions
    accordingly.

    Supported operator commands:
    - /n: Start a new context window
    - /p: Display the developer prompt
    - /m: Display the command menu
    - /r: Reload the developer prompt
    - /c: Send a command to the device directly
    - /q: Quit the program

    If the input query does not match any of the supported commands, a
    ValueError is raised.

    The function returns the updated operator command parameters after
    processing the user input.
    """
    if operator_cmd_params["user_input"] == "":
        return operator_cmd_params

    # Start a new context window
    if operator_cmd_params["input_query"].startswith("/n"):
        log.info("New context window started.\n")
        operator_cmd_params["user_input"] = [
            {
                "role": "developer",
                "content": operator_cmd_params["prompt"],
            }
        ]
        operator_cmd_params["context_depth"] = 0

    # Display the developer prompt
    elif operator_cmd_params["input_query"].startswith("/p"):
        print()
        pydoc.pager(operator_cmd_params["prompt"])
        print()

    # Display the command menu
    elif operator_cmd_params["input_query"].startswith("/m"):
        menu()

    # Reload the developer prompt
    elif operator_cmd_params["input_query"].startswith("/r"):
        operator_cmd_params["prompt"] = developer_input_prompt(
            operator_cmd_params["prompt_file"]
        )
        log.info("Prompt reloaded.")
        log.info("New context window started.\n")
        operator_cmd_params["user_input"] = [
            {
                "role": "developer",
                "content": operator_cmd_params["prompt"],
            }
        ]
        operator_cmd_params["context_depth"] = 0

    # Send a command to the device directly
    elif operator_cmd_params["input_query"].startswith("/c"):
        parse_command_re = re.compile(r"^/c\s+(.+)")
        if match := parse_command_re.search(
            operator_cmd_params["input_query"]
        ):
            command = match.group(1)
            command_resp = handle_command(operator_cmd_params["conn"], command)
            pydoc.pager(command_resp)
            print()
        else:
            log.error("Could not parse the command.\n")

    # Quit the program
    elif operator_cmd_params["input_query"].startswith("/q"):
        log_total_tokens(operator_cmd_params["total_tokens"])
        handle_disconnect(
            operator_cmd_params["conn"], operator_cmd_params["host"]
        )
        sys.exit(0)

    return operator_cmd_params


def iosxe_chat_loop(conn, host, prompt_file):
    """
    Function to initiate a chat loop with an IOSXE device.

    Parameters:
    - conn: SSH connection object to the device
    - host: IP address or hostname of the device
    - prompt_file: File containing prompts for the chat loop

    Returns:
    - None

    Raises:
    - OpenAIError: If there is an error with the OpenAI API
    - JSONDecodeError: If there is an error decoding JSON data
    - ConnectionException: If there is an issue with the SSH connection
    - socket.error: If there is a socket error
    - Exception: For any other unhandled exceptions

    This function sets up a chat loop with an IOSXE device using the provided
    SSH connection object and prompts from a file. It prompts the user for
    input, processes the input, and interacts with the device accordingly. The
    loop continues until an error occurs or the user decides to exit.
    """
    iosxe_chat_loop_params = {
        "conn": conn,
        "host": host,
        "context_depth": 0,
        "prompt_file": prompt_file,
        "total_tokens": 0,
        "prompt": developer_input_prompt(prompt_file),
    }

    token_count = 0

    menu()

    iosxe_chat_loop_params["user_input"] = [
        {"role": "developer", "content": iosxe_chat_loop_params["prompt"]}
    ]
    while True:
        try:
            iosxe_chat_loop_params["input_query"] = operator_prompt(
                iosxe_chat_loop_params
            )
            print()

            # parse the escaped commands from the user
            if (
                iosxe_chat_loop_params["input_query"].startswith("/")
                or iosxe_chat_loop_params["input_query"] == ""
            ):
                iosxe_chat_loop_params = operator_cmds(iosxe_chat_loop_params)
                continue

            log.info(f"Query to LLM: {iosxe_chat_loop_params['input_query']}")

            iosxe_chat_loop_params["user_input"].append(
                {
                    "role": "user",
                    "content": iosxe_chat_loop_params["input_query"],
                }
            )

            iosxe_chat_loop_params["context_depth"] += 1

            reply, token_count = handle_llm_api(
                iosxe_chat_loop_params["user_input"]
            )
            if reply == {}:
                log.error("Received an empty dict from handle_llm_api().")
                continue

            iosxe_chat_loop_params["total_tokens"] += token_count

            if "answer" in reply.keys():
                iosxe_chat_loop_params["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )
                pydoc.pager(reply["answer"])
                print()
                continue

            elif "command" in reply.keys():
                iosxe_chat_loop_params["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )

                command_resp = ""
                for command in reply["command"]:
                    command_resp += handle_command(
                        iosxe_chat_loop_params["conn"], command
                    )

                iosxe_chat_loop_params["user_input"].append(
                    {
                        "role": "user",
                        "content": str(command_resp),
                    }
                )

            reply, token_count = handle_llm_api(
                iosxe_chat_loop_params["user_input"]
            )
            if reply == {}:
                log.error("Received an empty dict from handle_llm_api().")
                continue

            iosxe_chat_loop_params["total_tokens"] += token_count
            if "answer" in reply.keys():
                print()
                pydoc.pager(reply["answer"])
                print()

                iosxe_chat_loop_params["user_input"].append(
                    {
                        "role": "assistant",
                        "content": str(reply),
                    }
                )
            elif "configure" in reply.keys():
                print()
                pydoc.pager("\n".join([line for line in reply["configure"]]))
                print()
                if commit_change() is False:
                    print("Discarding changes.\n")
                    continue

                conf_resp = (
                    handle_configure(
                        iosxe_chat_loop_params["conn"],
                        reply["configure"],
                    )
                    or ""
                )
                print()
                pydoc.pager(conf_resp)
                print()

        except OpenAIError as e:
            log.error(f"Caught OpenAIError: {e}.")
        except (json.JSONDecodeError, json.decoder.JSONDecodeError) as e:
            log.error(f"Caught JSONDecodeError: {e}")
        except ConnectionException as e:
            log.error(f"ConnectionException in iosxe_chat_loop(): {e}")
            sys.exit(1)
        except s_error as e:
            log.error(f"socket.error in iosxe_chat_loop(): {e}")
            sys.exit(1)
        except Exception as e:
            log.error(f"Unhandled exception in iosxe_chat_loop(): {e}")


def main():
    clear_screen()

    main_params = {
        # get the host from the user cli args
        "host": handle_command_line_args(),
        "username": os.environ["TESTBED_USERNAME"],
        "password": os.environ["TESTBED_PASSWORD"],
    }

    prompt_file = "iosxe_prompt.md"
    if not os.path.exists(prompt_file):
        log.error(f"File {prompt_file} does not exist.")
        sys.exit(1)

    conn = handle_connect(main_params)

    try:
        total_tokens = iosxe_chat_loop(conn, main_params["host"], prompt_file)
        log_total_tokens(total_tokens)
        handle_disconnect(conn, main_params["host"])
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt....exiting.")
        handle_disconnect(conn, main_params["host"])
    except Exception as e:
        log.error(f"Exception caught in main(): {e}")


if __name__ == "__main__":
    main()
