import ast
import os
import platform
import pydoc
import re
import readline
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
_ = readline

# set the logging
log = logger("info")

# set the pager to be used
os.environ["PAGER"] = "more"


# allows the use of the arrow keys for navigating the command line/history
def readline_input(prompt=""):
    """
    Reads a line of input from the user, displaying an optional prompt.

    This function wraps the built-in `input` function to safely handle
    `EOFError` exceptions, which can occur if the input stream is closed
    unexpectedly (e.g., when the user sends an EOF signal like Ctrl-D on Unix
    or Ctrl-Z on Windows). In such cases, the function returns an empty string
    instead of raising an exception, allowing the program to continue running
    smoothly.

    Parameters:
    ----------
    prompt : str, optional
        A string to be displayed as a prompt to the user. Defaults to an empty
        string, meaning no prompt will be shown if not specified.

    Returns:
    -------
    str
        The line of input entered by the user, or an empty string if an
        `EOFError` is encountered.

    Examples:
    --------
    >>> name = readline_input("Enter your name: ")
    Enter your name: John
    >>> print(name)
    John

    >>> # Simulating EOFError by sending EOF signal
    >>> readline_input("Enter something: ")
    Enter something:
    ''

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


def handle_command_line_args():
    """
    Parse and validate command-line arguments for the iosxe_chatbot script.

    This function checks the number of command-line arguments provided to the
    script. It expects exactly one argument, which is the device IP or name.
    If the number of arguments is incorrect, it prints the usage message to
    standard error and exits the program with a status code of 1.

    Returns:
        str: The device IP or name provided as a command-line argument.

    Raises:
        SystemExit: If the number of command-line arguments is not equal to 2.

    Usage:
        python iosxe_chatbot.py <device IP/name>
    """
    usage = "Usage: python iosxe_chatbot.py <DEVICE_IP_OR_HOSTNAME>"
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
    handle_connect(device_params)

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

    Example: >>> response = handle_command(conn, "show version") >>>
    print(response) Cisco IOS Software, C2960S Software (C2960S-UNIVERSALK9-M),
    Version 15.0(2)SE11, RELEASE SOFTWARE (fc1)

    >>> response = handle_command(conn, "show ip interface brief?") >>>
    print(response) Interface              IP-Address      OK? Method Status
    Protocol Vlan1                  unassigned      YES unset  administratively
    down down FastEthernet0/1        unassigned      YES unset  up
    up
    """
    device_prompt = ios_prompt(conn)
    try:
        if re.search(r".+\?$", command):
            conn.write_channel(command + "\n")
            sleep(0.1)
            resp = conn.read_channel()
            resp = resp.replace(command, "")
            resp = resp.replace(device_prompt, "")
            resp = resp.replace("% Incomplete command.", "")
            resp = resp.replace(command.replace("?", ""), "")
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
        log.error(f"AttributeError in handle_command(): {e}")
    except re.error as e:
        log.error(f"re.error in handle_command(): {e}")
    except Exception as e:
        log.error(f"Unhandled exception in handle_command(): {e}")


def handle_configure(conn, conf_list):
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
    >>> reply, tokens = handle_llm_api("What is the capital of France?")
    >>> print(reply)
    {'answer': 'Paris'}
    >>> print(tokens)
    15
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

            reply = ast.literal_eval(response.output_text)

            return reply, total_tokens

    except OpenAIError as e:
        log.error(f"OpenAIError: {e}")
    except ValueError as e:
        log.error(f"ValueError in handle_llm_api(): {e}")
    except SyntaxError as e:
        log.error(f"SyntaxError in handle_llm_api(): {e}")
    except Exception as e:
        log.error(f"Unhandled exception in handle_llm_api(): {e}")

    return {}, 0


def operator_cmds(operator_cmd_params):
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
      `menu()`, `developer_input_prompt()`, `handle_command()`,
      `log_total_tokens()`, and `handle_disconnect()` which are not defined
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
            pydoc.pager(str(command_resp))
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
            # prompt the operator
            iosxe_chat_loop_params["input_query"] = operator_prompt(
                iosxe_chat_loop_params
            )
            print()

            # parse the escaped commands from the operator
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

            # continue to process "command" responses from the LLM until its
            # done
            while "command" in reply.keys():
                iosxe_chat_loop_params["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )

                command_resp = ""
                for command in reply["command"]:
                    command_resp += str(
                        handle_command(iosxe_chat_loop_params["conn"], command)
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
                iosxe_chat_loop_params["total_tokens"] += token_count

                if reply == {}:
                    log.error("Received an empty dict from handle_llm_api().")
                    break

            # process answer responses
            if "answer" in reply.keys():
                iosxe_chat_loop_params["user_input"].append(
                    {"role": "assistant", "content": str(reply)}
                )
                buffer = StringIO()
                console = Console(file=buffer, width=80)
                console.print(Markdown(reply["answer"]))
                md = buffer.getvalue()
                print()
                pydoc.pager(md)
                print()

            # process configure responses
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

            iosxe_chat_loop_params["total_tokens"] += token_count

        except OpenAIError as e:
            log.error(f"Caught OpenAIError: {e}.")
        except ConnectionException as e:
            log.error(f"ConnectionException in iosxe_chat_loop(): {e}")
            sys.exit(1)
        except s_error as e:
            log.error(f"socket.error in iosxe_chat_loop(): {e}")
            sys.exit(1)
        except Exception as e:
            log.error(f"Unhandled exception in iosxe_chat_loop(): {e}")


def main():
    host = handle_command_line_args()
    clear_screen()

    main_params = {
        # get the host from the user cli args
        "host": host,
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
