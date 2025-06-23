# IOS-XE Chatbot

IOS-XE Chatbot is a Python-based interactive CLI assistant that connects a local terminal to a Cisco IOS-XE router or switch using the OpenAI GPT-4o LLM. It enables natural language interaction with the device, translating user queries into IOS-XE commands and configurations.

## Features

- Uses OpenAI GPT-4o API to process natural language queries
- Interfaces with Cisco IOS-XE devices via `pyATS` and `Unicon`
- Supports context-aware conversations
- JSON-based response handling (commands, answers, or configurations)
- Extensible prompt design via markdown template
- Command menu for interactive use

## Requirements

Install dependencies using `requirements.txt`:

```bash
pip install -r requirements.txt
```

Ensure the following are installed:
- Python 3.8+
- Access to Cisco device(s) defined in a `testbed.yaml`
- OpenAI API Key

## Files

- `iosxe_chatbot.py`: Main program logic and LLM interface
- `iosxe_prompt.md`: Developer/system prompt for LLM role definition
- `testbed.yaml`: PyATS-compatible device connection configuration
- `requirements.txt`: Dependency list
- `LICENSE`: Project license

## Usage

1. Export your OpenAI API key:

```bash
export OPENAI_API_KEY="your-api-key"
```

2. Prepare your `testbed.yaml` file in the working directory.

3. Run the chatbot:

```bash
python iosxe_chatbot.py
```

4. Use the CLI menu for interacting with the assistant:

```
/command - run a command directly on the device
/menu    - print the menu
/new     - start a new context window
/prompt  - print the developer prompt
/quit    - exit the program
```

Ask questions about the device like:

```
What is the IP address of interface GigabitEthernet1?
```

The assistant will reply with:
- JSON command if input is needed from the device
- JSON answer if an answer can be given
- JSON configuration to be applied (if appropriate)

## Prompt Design

Responses are expected in valid JSON:

- Command: `{"command": ["show version"]}`
- Answer: `{"answer": "The device uptime is 5 days."}`
- Configuration: `{"configure": ["interface Lo1", "ip address 1.1.1.1 255.255.255.0"]}`

See `iosxe_prompt.md` for full schema and examples.

## License

See [LICENSE](./LICENSE) for license details.
