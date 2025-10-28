import argparse
import ast
import ctypes
import getpass
import os
import platform
import pydoc
import re
import sys
from io import StringIO
from lib.menu import menu
from lib.logs import logger
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetMikoTimeoutException,
    NetMikoAuthenticationException,
    ConfigInvalidException,
    ConnectionException,
)
from openai import OpenAI, OpenAIError
from rich.console import Console
from rich.markdown import Markdown
from socket import error as s_error
from time import sleep

# suppress the linter warning for importing without use
# this allows the use of arrow keys to navigate the cli
if platform.system() != "Windows":
    import readline

    _ = readline

log = logger("info")

os.environ["PAGER"] = "more"

# List of models available, don't forget to update the menu() text with
# any changes to the modle list
MODELS = {
    1: "gpt-5-mini",
    2: "gpt-5",
    3: "gpt-5-nano",
}


# allows the use of the arrow keys for navigating the command line/history
def safe_input(prompt=""):
    """
    Notes:
    -----
    This function is particularly useful in interactive scripts where user
    input is required, and it is important to handle unexpected EOF signals
    gracefully.
    """
    try:
        return input(prompt)
    except EOFError:
        return ""


def parse_args():
    """
    Parse and validate command-line arguments for connecting to a Cisco IOS-XE
    device.

    This function uses argparse to handle input parameters for an AI chatbot
    that interacts with Cisco IOS-XE devices. It enforces mutually exclusive
    authentication methods and ensures all required credentials are provided
    either via command-line arguments or environment variables.

    Returns: dict: A dictionary containing the following keys:
            - "host" (str): IP address or hostname of the Cisco IOS-XE device.
            - "username" (str): Username for device authentication.
            - "password" (str): Password for device authentication.

    Raises: SystemExit: If argument parsing fails or required environment
    variables are missing.
            - If both `--env` and `--username` are provided simultaneously.
            - If `--password` is provided without `--username`.
            - If `--env` is specified but the environment variables
              `IXC_USERNAME` or `IXC_PASSWORD` are not set or empty.

    Behavior:
        - Requires the positional argument `host`.
        - Requires exactly one of the following authentication methods: *
          `--env`: Use environment variables `IXC_USERNAME` and `IXC_PASSWORD`.
          * `--username` (with optional `--password`): Use provided username
          and password. If password is omitted, prompts interactively.
        - Validates mutual exclusivity and dependency of arguments.
        - Prompts for password interactively if `--username` is provided
          without `--password`.

    Example usage:
        python ixc.py 192.168.1.1 --env
        python ixc.py device.example.com -u admin -p secret123
        python ixc.py device.example.com -u admin

    Note: This function calls `sys.exit()` internally on argument errors or
    missing environment variables, terminating the program with an error
    message.
    """
    main_params = {}

    p = argparse.ArgumentParser(
        description=(
            "An AI chatbot for interacting with a Cisco IOS-XE devices,"
        )
    )
    group = p.add_mutually_exclusive_group(required=True)
    p.add_argument(
        "host",
        type=str,
        help="IP address or hostname of the Cisco IOS-XE device to chat with.",
    )
    group.add_argument(
        "-e",
        "--env",
        action="store_true",
        required=False,
        help=(
            "Device credentials are provided through environment variables "
            "IXC_USERNAME and IXC_PASSWORD"
        ),
    )
    group.add_argument(
        "-u",
        "--username",
        type=str,
        help="Device username.",
    )
    p.add_argument(
        "-p",
        "--password",
        type=str,
        nargs="?",
        const=None,
        help="Device password.",
    )

    args = p.parse_args()

    if args.username and args.env:
        p.error("Error: cannot not use -u/--username with -e/--env")

    if args.password and not args.username:
        p.error("-p/--password can only be used with -u/--username")

    main_params["host"] = args.host

    if args.env:
        main_params["username"] = os.environ["IXC_USERNAME"]

        pw_str = os.environ["IXC_PASSWORD"]
        main_params["password"] = ctypes.create_string_buffer(
            pw_str.encode("utf-8")
        )

        if not main_params["username"] or not main_params["password"]:
            sys.exit("Missing USERNAME and PASSWORD environment variables")
    else:
        main_params["username"] = args.username

        pw_str = args.password or getpass.getpass("Password: ")
        main_params["password"] = ctypes.create_string_buffer(
            pw_str.encode("utf-8")
        )

    return main_params


def clear_terminal():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def load_prompt_from_file(filename):
    with open(filename, "r") as f:
        prompt = f.read()
    return prompt


def get_device_prompt(conn):
    return conn.find_prompt()


def log_session_tokens(total_tokens):
    print()
    log.info(f"Total tokens consumed for the session {total_tokens}")


def confirm_config_change():
    operator_permission = safe_input("Commit changes [y/n]: ")
    if operator_permission.lower() == "y":
        return True
    elif operator_permission.lower() == "n":
        return False
    else:
        return confirm_config_change()


def get_operator_input(get_operator_input_params):
    model = get_operator_input_params["model"]
    device_prompt = get_device_prompt(get_operator_input_params["conn"])
    prompt_text = f"[IOS-XE Chatbot]-[{model}]"

    prompt = f"┌──[{get_operator_input_params['context_depth']}]-{prompt_text}"

    print(prompt)
    operator_input = safe_input(f"└─ {device_prompt} ")

    return operator_input


def format_answer(reply):
    if platform.system() == "Windows":
        return reply

    buffer = StringIO()
    console = Console(file=buffer, width=80)
    console.print(Markdown(reply))
    md = buffer.getvalue()

    return md


def get_device_info(conn):
    """
    Retrieve and format device information from a network device connection.

    This function sends two commands, "show version" and "show platform", to
    the device via the provided connection object. It parses the command
    outputs to extract the IOS-XE software version and the chassis type, then
    returns this information formatted as a JSON-like string enclosed in
    markdown code block syntax.

    Parameters ---------- conn : object An active connection object to the
    network device. This object must be compatible with the
    `send_device_command` function, which is expected to send commands to the
    device and return their output as strings.

    Returns ------- str A string containing the extracted device information
    formatted as a JSON object within a markdown code block. For example:

        ```json { "IOS-XE Version": "17.3.1", "Chassis": "C9300-24T" } ```

        If the expected information cannot be found in the command outputs, the
        returned JSON object may be incomplete or empty.

    Raises ------ Any exceptions raised by `send_device_command` or by the
    connection object are propagated. For example, connection errors, command
    execution failures, or timeouts may raise exceptions.

    Notes -----
    - The function uses regular expressions to parse the command outputs.
    - The function assumes that the `send_device_command` function and `conn`
      are defined and implemented elsewhere in the codebase.
    - The returned string is intended for display or logging purposes and is
      not a Python dictionary or JSON object.

    Example ------- >>> device_info = get_device_info(conn) >>>
    print(device_info) ```json { "IOS-XE Version": "17.3.1", "Chassis":
    "C9300-24T" } ```
    """
    show_version = send_device_command(conn, "show version")
    show_platform = send_device_command(conn, "show platform")

    device_info = "```json\n"

    if match := re.search(r"Version +(\d+\.\d+\.\d+\w*)", str(show_version)):
        version = match.group(1)
        device_info += f'{{\n    "IOS-XE Version": "{version}",\n'

    if match := re.search(r"Chassis type: (.+)", str(show_platform)):
        chassis = match.group(1)
        device_info += f'    "Chassis": "{chassis}"\n}}\n\n'

    device_info += "```"

    return device_info


def connect_to_device(device_params):
    """
    Establishes a connection to a network device using the provided parameters.

    This function attempts to create a connection to a network device using the
    Netmiko library's `ConnectHandler`. It requires a dictionary of device
    parameters, including host, username, and password. The connection is
    specifically tailored for Cisco IOS devices.

    Parameters: ---------- device_params : dict A dictionary containing the
    connection parameters for the device. It must include the following keys:
        - "host" (str): The IP address or hostname of the device.
        - "username" (str): The username for authentication.
        - "password" (str): The password for authentication.

    Returns: ------- ConnectHandler An instance of Netmiko's ConnectHandler if
    the connection is successfully established.

    Raises: ------ SystemExit If any exception occurs during the connection
    attempt, the function logs the error and exits the program with a status
    code of 1. The possible exceptions include:
        - NetMikoAuthenticationException: Raised when authentication fails.
        - ConnectionException: Raised for general connection issues.
        - NetMikoTimeoutException: Raised when the connection attempt times
          out.
        - Exception: Catches any other unhandled exceptions.

    Example: ------- >>> device_params = { >>>     "host": "192.168.1.1", >>>
    "username": "admin", >>>     "password": "admin123" >>> } >>> connection =
    connect_to_device(device_params)

    Notes: -----
    - Ensure that the Netmiko library is installed and properly configured in
      your environment.
    - This function is designed for Cisco IOS devices; using it with other
      device types may require modifications.
    """
    try:
        conn = ConnectHandler(
            host=device_params["host"],
            port=22,
            username=device_params["username"],
            password=device_params["password"].value,
            device_type="cisco_ios",
            timeout=10,
        )

        ctypes.memset(
            ctypes.addressof(device_params["password"]),
            0,
            len(device_params["password"]),
        )
        del device_params["password"]

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


def send_device_command(conn, command):
    """
    Sends a command to a network device and retrieves the response.

    This function handles the execution of a command on a network device
    through a given connection object. It determines whether the command
    is a query (ends with a question mark) or a standard command and
    processes it accordingly. For query commands, it writes the command
    directly to the channel and reads the response. For standard commands,
    it uses the `send_command` method of the connection object to send
    the command and capture the response.

    Parameters:
    conn (object): A connection object that provides methods to interact
                   with the network device. It must have `write_channel`
                   and `read_channel` methods for query commands, and a
                   `send_command` method for standard commands.
    command (str): The command string to be sent to the network device.
                   It can be a query (ending with '?') or a standard
                   command.

    Returns:
    str: The response from the network device after executing the command.
         For query commands, the command itself is stripped from the
         response.

    Raises:
    AttributeError: If the connection object does not have the required
                    methods (`write_channel`, `read_channel`, or
                    `send_command`).
    re.error: If there is an error in compiling the regular expression
              used to detect the command prompt.

    Example: >>> response = send_device_command(conn, "show version") >>>
    print(response) Cisco IOS Software, C2960S Software (C2960S-UNIVERSALK9-M),
    Version 15.0(2)SE11, RELEASE SOFTWARE (fc1)

    >>> response = send_device_command(conn, "show ip interface brief?") >>>
    print(response) Interface              IP-Address      OK? Method Status
    Protocol Vlan1                  unassigned      YES unset  administratively
    down down FastEthernet0/1        unassigned      YES unset  up
    up
    """
    device_prompt = get_device_prompt(conn)

    # list of strings used to clean up raw output
    conn_read_replace_strings = [
        command,
        device_prompt,
        "% Incomplete command.",
        command.replace("?", ""),
        "\n\n",
    ]

    try:
        if re.search(r".+\?$", command):
            conn.write_channel(command + "\n")
            sleep(0.1)
            resp = conn.read_channel()

            for string in conn_read_replace_strings:
                resp = resp.replace(string, "")

            return resp

        expect_re = re.compile(r"[#>?:]\s*$")
        resp = conn.send_command(
            command_string=command,
            expect_string=expect_re,
            strip_prompt=True,
            strip_command=True,
        )

        return resp

    except AttributeError as e:
        log.error(f"AttributeError in send_device_command(): {e}")
    except re.error as e:
        log.error(f"re.error in send_device_command(): {e}")
    except Exception as e:
        log.error(f"Unhandled exception in send_device_command(): {e}")


def send_config_to_device(conn, conf_list):
    """
    Sends a set of configuration commands to a network device and handles
    potential exceptions.

    This function attempts to send a list of configuration commands to a
    network device using the provided connection object. It logs the outcome of
    the operation, whether successful or if an exception occurs.

    Parameters: ---------- conn : object A connection object that provides the
    `send_config_set` method to send configuration commands to a network
    device. This object is expected to handle the communication with the
    device.

    conf_list : list of str A list of configuration commands to be sent to the
    network device. Each command should be a string representing a valid
    configuration command for the device.

    Returns: ------- str The response from the network device after sending the
    configuration commands. This is typically a string indicating the result of
    the configuration operation.

    Raises: ------ ConfigInvalidException If the configuration commands are
    invalid or cannot be applied to the device. This exception is logged with
    an error message.

    Exception Any other unhandled exceptions that occur during the
    configuration process are caught and logged with an error message.

    Notes: -----
    - Ensure that the `conn` object is properly initialized and connected to
      the target network device before calling this function.
    - The function logs messages using a logger named `log`, which should be
      configured in the calling context to capture and store log messages
      appropriately.
    """
    try:
        resp = conn.send_config_set(conf_list)
        log.info("Configuration successully.")
        return resp
    except ConfigInvalidException as e:
        log.error(f"ConfigInvalidException: {e}")
    except Exception as e:
        log.error(f"Unhandled exception in send_config_to_device(): {e}")


def disconnect_device(conn, host):
    """
    Handles the disconnection of a connection to a host.
    """
    conn.disconnect()
    log.info(f"Connection to {host} closed.")


def query_llm_api(api_params):
    """
    Interacts with the OpenAI API to process a given user input and returns the
    response.

    This function takes a user input string, sends it to the OpenAI API using
    the specified model, and returns the API's response along with the total
    number of tokens used in the request. It handles various exceptions that
    may occur during the API interaction and logs relevant information for
    debugging purposes.

    Parameters: ---------- user_input : str The input string provided by the
    user that needs to be processed by the OpenAI API.

    Returns: ------- tuple A tuple containing:
        - reply (dict): The response from the OpenAI API, parsed as a
          dictionary. If an error occurs, an empty dictionary is returned.
        - total_tokens (int): The total number of tokens used in the API
          request. If an error occurs, zero is returned.

    Exceptions: ----------
    OpenAIError Raised when there is an issue with the OpenAI API request or
    response.
    ValueError Raised when there is an issue with evaluating the response
    text.
    SyntaxError Raised when there is a syntax error in the response text.
    Exception Catches any other unhandled exceptions that may occur.

    Notes: -----
    - Ensure that the environment variable 'OPENAI_API_KEY' is set with a valid
      API key before calling this function.
    - The function logs the total number of tokens used and the reply from the
      API for debugging purposes.
    - The function uses the 'gpt-4o' model for processing the input.

    Example:
    -------
    >>> reply, tokens = query_llm_api("What is the capital of France?")
    >>> print(reply)
    {'answer': 'Paris'}
    >>> print(tokens)
    15
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model=api_params["model"],
            input=api_params["user_input"],
        )
        if response is not None:
            total_tokens = 0
            if response.usage is not None:
                log.info(f"Total Tokens: {response.usage.total_tokens}")
                total_tokens += response.usage.total_tokens

            log.info(f"Reply from the LLM API: {response.output_text}")

            reply = ast.literal_eval(response.output_text)

            return reply, total_tokens

    except OpenAIError as e:
        log.error(f"OpenAIError: {e}")
    except ValueError as e:
        log.error(f"ValueError in query_llm_api(): {e}")
    except SyntaxError as e:
        log.error(f"SyntaxError in query_llm_api(): {e}")
    except Exception as e:
        log.error(f"Unhandled exception in query_llm_api(): {e}")

    return {}, 0


def process_operator_commands(operator_cmd_params):
    """
    Processes a set of operator commands based on user input and modifies the
    operator command parameters accordingly.

    This function interprets the user's input query and performs actions such
    as starting a new context window, displaying prompts, reloading prompts,
    sending commands to a device, or quitting the program. It updates the
    `operator_cmd_params` dictionary based on the command executed.

    Parameters: ----------
        operator_cmd_params : dict A dictionary containing
        the following keys:
            - "user_input" (str): The current user input.
            - "input_query" (str): The query string to be processed.
            - "prompt" (str): The developer prompt to be displayed or reloaded.
            - "prompt_file" (str): The file path to reload the developer prompt
              from.
            - "conn" (object): The connection object to send commands to a
              device.
            - "host" (str): The host address for the connection.
            - "total_tokens" (int): The total number of tokens processed.
            - "context_depth" (int): The current depth of the context window.

    Returns: -------
        dict The updated `operator_cmd_params` dictionary after processing the
        input query.

    Raises: ------
        SystemExit If the input query starts with "/q", the program will exit.

    Notes: -----
    - If the `user_input` is an empty string, the function returns the input
      `operator_cmd_params` without any modifications.
    - The function uses regular expressions to parse commands that start with
      "/c".
    - The function logs various actions and errors using a logging mechanism.
    - The function uses `pydoc.pager` to display content in a paginated manner.
    - The function assumes the existence of external functions such as
      `menu()`, `load_prompt_from_file()`, `send_device_command()`,
      `log_session_tokens()`, and `disconnect_device()` which are not defined
      within this code snippet.
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
        operator_cmd_params["prompt"] = load_prompt_from_file(
            operator_cmd_params["prompt_file"]
        )
        log.info("Prompt reloaded.")
        log.info("New context window started.\n")

        operator_cmd_params["prompt"] += get_device_info(
            operator_cmd_params["conn"]
        )

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
            command_resp = send_device_command(
                operator_cmd_params["conn"], command
            )
            pydoc.pager(str(command_resp))
            print()
        else:
            log.error("Could not parse the command.\n")

    # Select model
    elif operator_cmd_params["input_query"].startswith("/s"):
        if match := re.search(
            r"^/s\s+(\d+)", operator_cmd_params["input_query"]
        ):
            model_key = match.group(1)
            if int(model_key) in MODELS.keys():
                operator_cmd_params["model"] = MODELS[int(model_key)]
            else:
                menu()
                print("% Bad model selection.\n")
        else:
            menu()
            print("% Bad model selection.\n")

    # Quit the program
    elif operator_cmd_params["input_query"].startswith("/q"):
        log_session_tokens(operator_cmd_params["total_tokens"])
        disconnect_device(
            operator_cmd_params["conn"], operator_cmd_params["host"]
        )
        sys.exit(0)

    return operator_cmd_params


def process_llm_commands(conn, commands):
    """
    Processes a list of commands intended for a device connection, filtering
    out forbidden commands, sending allowed commands to the device, and
    aggregating their responses.

    This function iterates over each command in the provided list, checks if
    the command matches a set of forbidden patterns (commands starting with
    "co" or "re", case-insensitive). If a command is forbidden, it logs an
    error and appends a special forbidden command message to the response
    string. Otherwise, it sends the command to the device via the
    `send_device_command` function and appends the command's response to the
    aggregated response string.

    Parameters ---------- conn : object An active connection object to the
    target device. The exact type depends on the device communication interface
    and must be compatible with the `send_device_command` function. commands :
    list of str A list of command strings to be processed and sent to the
    device.

    Returns ------- str A concatenated string containing the responses from the
    device for each allowed command, interleaved with messages indicating any
    forbidden commands encountered.

    Raises ------ Exception Any exceptions raised by `send_device_command` are
    propagated upwards. This function does not handle exceptions from the
    device communication layer internally.

    Notes -----
    - The forbidden commands are identified by a regex pattern that matches any
      command starting with "co", "re" or "de" (case-insensitive). This pattern
      can be adjusted as needed.
    - Logging is performed at the error level for any forbidden commands
      detected.
    - The function assumes the existence of a `send_device_command(conn,
      command)` function that sends a command to the device and returns its
      response.

    Example ------- >>> conn = create_device_connection() >>> commands =
    ["status", "connect", "reset", "info"] >>> response =
    process_llm_commands(conn, commands) >>> print(response) %FORBIDDEN
    COMMAND: connect %FORBIDDEN COMMAND: reset <response for status><response
    for info>
    """
    # matching copy, configure, reload, debug and delete
    forbidden = re.compile(r"^co.+|^re.+|^de.+", re.IGNORECASE)
    command_resp = ""
    for command in commands:
        if forbidden.search(command):
            log.error(f"FORBIDDEN COMMAND from LLM {command}")
            command_resp += f"%%FORBIDDEN COMMAND: {command}"
        else:
            command_resp += str(send_device_command(conn, command))

    return command_resp


def run_chat_loop(conn, host, prompt_file):
    """
    Initiates and manages an interactive chat loop with an IOS-XE device using
    a language model for processing and responding to user inputs.

    This function sets up a continuous loop where user inputs are processed
    and responded to by a language model. It handles various types of responses
    such as commands, answers, and configuration changes, and manages the
    interaction with the IOS-XE device accordingly.

    Parameters:
    conn (object): The connection object to the IOS-XE device.
    host (str): The hostname or IP address of the IOS-XE device.
    prompt_file (str): The file path to the prompt file used for initializing
                       the chat context.

    Raises:
    OpenAIError: If an error occurs while interacting with the language model
                 API.
    ConnectionException: If there is a connection issue with the IOS-XE device.
    socket.error: If a socket error occurs during the operation.
    Exception: For any other unhandled exceptions that may arise.

    Note:
    The function will continue to run indefinitely until manually stopped or
    an unhandled exception causes it to exit.
    """
    run_chat_loop_params = {
        "conn": conn,
        "host": host,
        "context_depth": 0,
        "prompt_file": prompt_file,
        "total_tokens": 0,
        "prompt": load_prompt_from_file(prompt_file),
        "model": MODELS[1],
    }

    token_count = 0

    menu()

    run_chat_loop_params["prompt"] += get_device_info(conn)

    run_chat_loop_params["user_input"] = [
        {"role": "developer", "content": run_chat_loop_params["prompt"]}
    ]
    while True:
        try:
            # prompt the operator
            run_chat_loop_params["input_query"] = get_operator_input(
                run_chat_loop_params
            )
            print()

            # parse the escaped commands from the operator
            if (
                run_chat_loop_params["input_query"].startswith("/")
                or run_chat_loop_params["input_query"] == ""
            ):
                run_chat_loop_params = process_operator_commands(
                    run_chat_loop_params
                )
                continue

            log.info(f"Query to LLM: {run_chat_loop_params['input_query']}")

            run_chat_loop_params["user_input"].append(
                {
                    "role": "user",
                    "content": run_chat_loop_params["input_query"],
                }
            )

            run_chat_loop_params["context_depth"] += 1

            reply, token_count = query_llm_api(run_chat_loop_params)

            if reply == {}:
                log.error("Received an empty dict from query_llm_api().")
                continue

            # continue to process "command" responses from the LLM until its
            # done
            while "command" in reply.keys():
                run_chat_loop_params["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )

                command_resp = process_llm_commands(
                    run_chat_loop_params["conn"], reply["command"]
                )
                if "%%FORBIDDEN COMMAND" in command_resp:
                    break

                run_chat_loop_params["user_input"].append(
                    {
                        "role": "user",
                        "content": str(command_resp),
                    }
                )

                reply, token_count = query_llm_api(run_chat_loop_params)

                run_chat_loop_params["total_tokens"] += token_count

                if reply == {}:
                    log.error("Received an empty dict from query_llm_api().")
                    break

            # process answer responses
            if "answer" in reply.keys():
                run_chat_loop_params["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )
                md = format_answer(reply["answer"])
                print()
                pydoc.pager(md)
                print()

            # process configure responses
            elif "configure" in reply.keys():
                print()
                pydoc.pager("\n".join([line for line in reply["configure"]]))
                print()

                if confirm_config_change() is False:
                    print("Discarding changes.\n")
                    continue

                conf_resp = (
                    send_config_to_device(
                        run_chat_loop_params["conn"],
                        reply["configure"],
                    )
                    or ""
                )
                print()
                pydoc.pager(conf_resp)
                print()

            run_chat_loop_params["total_tokens"] += token_count

        except OpenAIError as e:
            log.error(f"Caught OpenAIError: {e}.")
        except ConnectionException as e:
            log.error(f"ConnectionException in run_chat_loop(): {e}")
            sys.exit(1)
        except s_error as e:
            log.error(f"socket.error in run_chat_loop(): {e}")
            sys.exit(1)
        except Exception as e:
            log.error(f"Unhandled exception in run_chat_loop(): {e}")


def main():
    # host = parse_device_args()

    main_params = parse_args()

    clear_terminal()

    prompt_file = "ixc_prompt.md"
    if not os.path.exists(prompt_file):
        log.error(f"File {prompt_file} does not exist.")
        sys.exit(1)

    try:
        conn = connect_to_device(main_params)
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt....exiting.")
        sys.exit(1)
    except Exception as e:
        log.warning(f"Unhandled exception in main(): {e}")
        sys.exit(1)

    try:
        total_tokens = run_chat_loop(conn, main_params["host"], prompt_file)
        log_session_tokens(total_tokens)
        disconnect_device(conn, main_params["host"])
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt....exiting.")
        disconnect_device(conn, main_params["host"])
    except Exception as e:
        log.error(f"Exception caught in main(): {e}")


if __name__ == "__main__":
    main()
