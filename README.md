# Terminal IOSXE Chatbot

**Terminal-based chatbot assistant for Cisco IOS-XE devices powered by OpenAI GPT-4o**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)

## Description

**Terminal IOSXE Chatbot** is a terminal-driven assistant designed for network engineers to interact with Cisco IOS-XE routers and switches. It leverages the OpenAI GPT-4o API to provide intelligent responses and suggested commands, facilitating easier diagnostics, troubleshooting, and device configuration through a conversational interface.

The chatbot uses `Netmiko` for device interaction and integrates with OpenAI's API to process user queries and generate JSON-formatted command, answer, or configuration responses. It adheres to a strict prompt specification to ensure predictable, machine-parsable outputs.

## Features

- Live CLI interaction with Cisco IOS-XE devices via SSH
- OpenAI GPT-4o powered assistant trained to respond with JSON-formatted output
- Automatically executes commands and configuration changes based on LLM responses
- Paged terminal output and context window management
- Custom developer prompt specification
- Token usage tracking

## Demo

```bash
$ python iosxe_chatbot.py 192.0.2.1
┌──(0)-[IOS-XE Chatbot]
└─ R1#
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/splitnines/iosxe_chatbot.git
cd iosxe_chatbot
```

### 2. Install Dependencies (via `uv` or `pip`)

If you're using [uv](https://github.com/astral-sh/uv):

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Or with `pip`:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Export Environment Variables

```bash
export TESTBED_USERNAME=your_username
export TESTBED_PASSWORD=your_password
export OPENAI_API_KEY=your_openai_api_key
```

### 4. Run the Chatbot

```bash
python trixc.py <DEVICE_IP_OR_HOSTNAME>
```

## Prompt Design

The system prompt (`iosxe_prompt.md`) instructs the assistant to:

- Respond with structured JSON
- Suggest CLI commands to execute on the Cisco device
- Output detailed answers when appropriate
- Ask for clarification if necessary
- Never combine `command`, `configure`, or `answer` keys in one response

Example:

```json
{"command": ["show ip interface brief"]}
```

```json
{"answer": "Interface is administratively down."}
```

```json
{"configure": ["interface Loopback0", "ip address 10.0.0.1 255.255.255.0"]}
```

## Commands

During interaction, you may use the following slash commands:

| Command | Description                     |
|---------|---------------------------------|
| `/n`    | Start a new context window      |
| `/p`    | View the developer prompt       |
| `/m`    | Display command menu            |
| `/r`    | Reload the developer prompt     |
| `/c`    | Execute a command directly      |
| `/q`    | Quit and disconnect             |

## Acknowledgements

- **Open Source Community** for Python and the rich ecosystem of libraries
- **John Capobianco**
[AutomateYourNetwork](https://github.com/automateyournetwork) for sharing his
work and inspiring this project.

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
